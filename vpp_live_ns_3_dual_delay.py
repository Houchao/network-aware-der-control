import numpy as np
from scipy.io import loadmat
from opendss_wrapper import OpenDSS
from live_plotter import LivePlotter


# Helpers

def mean_square_error(A, B, start_time=12*3600, end_time=14*3600):
    A = np.asarray(A).squeeze()
    B = np.asarray(B).squeeze()
    return np.mean((np.abs(A[start_time:end_time]) -
                    np.abs(B[start_time:end_time])) ** 2)

def projection_matlab(Pi, Qi, S_av, P_av):
    P_tmp = Pi.copy()
    Q_tmp = Qi.copy()

    for i in range(len(P_tmp)):
        if P_tmp[i] == 0 and Q_tmp[i] == 0:
            continue
        if S_av[i] <= 0:
            P_tmp[i] = 0
            Q_tmp[i] = 0
            continue

        Q_av_sq = S_av[i]**2 - P_av[i]**2
        Q_av = np.sqrt(max(Q_av_sq, 0.0))

        if Q_av == 0:
            P_tmp[i] = min(P_tmp[i], P_av[i])
            Q_tmp[i] = 0.0
            continue

        theta_c = np.arccos(np.clip(P_av[i] / Q_av, -1.0, 1.0))
        theta_i = np.arctan2(Q_tmp[i], P_tmp[i])

        if abs(theta_i) > abs(theta_c):
            mag = np.hypot(P_tmp[i], Q_tmp[i])
            if mag > Q_av and mag > 0:
                scale = S_av[i] / mag
                P_tmp[i] *= scale
                Q_tmp[i] *= scale
        else:
            if abs(Q_tmp[i]) > abs(Q_av * np.sin(theta_c)):
                P_tmp[i] = P_av[i]
                Q_tmp[i] = np.sign(Q_tmp[i]) * np.sqrt(
                    max(S_av[i]**2 - P_av[i]**2, 0)
                )
            elif P_tmp[i] > P_av[i]:
                P_tmp[i] = P_av[i]

    return P_tmp, Q_tmp

def load_p0_set_mat(path="P0_set.mat", var="set"):
    mat = loadmat(path)
    return np.array(mat[var]).squeeze()  # already NEGATIVE

def load_downlink_delay_csv(csv_path, num_der=18, num_steps=7200, drop_threshold_ms=100.0):
    lost_mask = np.zeros((num_der, num_steps), dtype=bool)

    with open(csv_path, "r") as f:
        for line in f:
            if not line.strip():
                continue
            t_sec, der_id, d_ms = line.strip().split(",")
            k = int(np.floor(float(t_sec)))
            j = int(der_id) - 1
            if 0 <= k < num_steps and float(d_ms) > drop_threshold_ms:
                lost_mask[j, k] = True

    return lost_mask


# Main
def run():

    d = OpenDSS("ieee37.dss")
    num_buses = d.get_NumBues()

    V_min = 0.95 * 4.8 / np.sqrt(3) * np.ones(num_buses)
    V_max = 1.05 * 4.8 / np.sqrt(3) * np.ones(num_buses)
    V_base = 4.8 / np.sqrt(3)

    P0_set = load_p0_set_mat("P0_set.mat")

    alpha, nu, epsilon, E = 0.05, 1e-3, 1e-6, 0.001
    cp, cq = 3.0, 1.0

    gamma_n = np.zeros(num_buses)
    mu_n    = np.zeros(num_buses)
    lamda   = np.zeros(num_buses)
    csi     = np.zeros(num_buses)

    G_busnums = [4,7,10,13,17,20,22,23,26,28,29,30,31,32,33,34,35,36]
    G = np.array(G_busnums) - 1

    P_av = np.zeros(num_buses)
    S_av = np.zeros(num_buses)
    P_av[G] = 110.0
    S_av[G] = 200.0
    S_av[9] = 300.0
    S_av[32] = 350.0
    S_av[33] = 350.0

    Y, _ = d.get_Ymatrix(show_y=False, phase="A")

    d.run_command("Clear")
    d.run_command("Compile ieee37.dss")
    d.run_command("Solve mode=snap")
    d.run_command("Set mode=daily stepsize=1s number=1")

    y_prime = np.zeros(num_buses, dtype=complex)
    y_prime[0] = complex(2475.093067, -8814.828164)

    num_pts = 24 * 3600
    start_ctrl, end_ctrl = 12*3600, 14*3600

    lost_mask = load_downlink_delay_csv("der_downlink_delay.csv", drop_threshold_ms=50.0)

    V_allbus = np.zeros((num_buses, num_pts), dtype=complex)
    P0 = np.zeros(num_pts)

    plotter = None
    count = 0

    # ========================================================
    # Control loop
    # ========================================================
    for k in range(num_pts):

        h = 1 if start_ctrl < k <= end_ctrl else 0

        V_hat = d.get_allbus_phase1_complex_kv()
        V_nom = V_hat if k < 2 else V_allbus[:, k-1]

        P0_hat, _ = d.get_circuit_power()
        V0 = d.get_v0_from_first_element()

        inj = np.conj(Y) @ np.conj(V_nom) + np.conj(y_prime) * np.conj(V0)
        S_nom = V_nom * inj

        gamma = np.diag(inj)
        Csi = np.diag(V_nom) @ np.conj(Y)

        H = np.linalg.inv(np.block([
            [np.real(gamma)+np.real(Csi), -np.imag(gamma)+np.imag(Csi)],
            [np.imag(gamma)+np.imag(Csi),  np.real(gamma)-np.real(Csi)]
        ]))

        ang = np.angle(S_nom)
        theta = np.hstack([np.diag(np.cos(ang)), np.diag(np.sin(ang))])
        AB = theta @ H
        A, B = AB[:, :num_buses], AB[:, num_buses:]

        Pi_hat = np.zeros(num_buses)
        Qi_hat = np.zeros(num_buses)
        for bus in G_busnums:
            p, q = d.get_power(f"PV{bus}", element="Generator", total=True)
            Pi_hat[bus-1], Qi_hat[bus-1] = p, q

        gamma_new = gamma_n + alpha*(V_min - np.abs(V_hat) - epsilon*gamma_n)
        mu_new    = mu_n    + alpha*(np.abs(V_hat) - V_max - epsilon*mu_n)

        lamda_new = lamda + alpha*(P0_hat - P0_set[k] - E - epsilon*lamda) if h else lamda.copy()
        csi_new   = csi   + alpha*(P0_set[k] - P0_hat - E - epsilon*csi)   if h else csi.copy()

        # ====================================================
        # MATLAB-equivalent rollback on delay
        # ====================================================
        if h and count < lost_mask.shape[1]:
            for j, bus in enumerate(G_busnums):
                b = bus - 1
                if lost_mask[j, count]:
                    gamma_new[b] = gamma_n[b]
                    mu_new[b]    = mu_n[b]
                    lamda_new[b] = lamda[b]
                    csi_new[b]   = csi[b]
            count += 1

        dual = -gamma_new + mu_new

        grad_P = 2*cp*(Pi_hat - P_av) + np.sum(A @ dual) + h*(lamda_new - csi_new) + nu*Pi_hat
        grad_Q = 2*cq*Qi_hat          + np.sum(B @ dual) + h*(lamda_new - csi_new) + nu*Qi_hat

        grad_P[~np.isin(np.arange(num_buses), G)] = 0.0
        grad_Q[~np.isin(np.arange(num_buses), G)] = 0.0

        Pi_next, Qi_next = projection_matlab(
            Pi_hat - alpha*grad_P,
            Qi_hat - alpha*grad_Q,
            S_av, P_av
        )

        if h:
            for bus in G_busnums:
                d.set_power(
                    name=f"PV{bus}",
                    p=float(-Pi_next[bus-1]),
                    q=float(-Qi_next[bus-1]),
                    element="Generator"
                )

        d.run_dss()
        P0[k] = d.get_circuit_power()[0]
        V_allbus[:, k] = d.get_allbus_phase1_complex_kv()

        # if k == start_ctrl:
        #     plotter = LivePlotter(P0_set, V_base, bus_idx=35, update_every=10)
        #
        # if h and plotter:
        #     plotter.update(k, P0, V_allbus)

        gamma_n, mu_n, lamda, csi = gamma_new, mu_new, lamda_new, csi_new

        if k % 3600 == 0:
            print(f"Hour {k//3600}")

    print("MSE:", mean_square_error(P0, P0_set))
    np.save("P0_delay.npy", P0)
    np.save("V_allbus_delay.npy", V_allbus)

if __name__ == "__main__":
    run()

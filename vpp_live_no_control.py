import numpy as np
from scipy.io import loadmat
from opendss_wrapper import OpenDSS

from live_plotter import LivePlotter

# ============================================================
# Helpers
# ============================================================

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
                Q_tmp[i] = np.sign(Q_tmp[i]) * np.sqrt(max(S_av[i]**2 - P_av[i]**2, 0))
            elif P_tmp[i] > P_av[i]:
                P_tmp[i] = P_av[i]

    return P_tmp, Q_tmp

def load_p0_set_mat(path="P0_set.mat", var="set"):
    mat = loadmat(path)
    return np.array(mat[var]).squeeze()   # already NEGATIVE in your file

# ============================================================
# Main
# ============================================================

def run():

    d = OpenDSS("ieee37.dss")
    num_buses = d.get_NumBues()

    # --------------------------------------------------------
    # Limits & parameters
    # --------------------------------------------------------
    V_min = 0.95 * 4.8 / np.sqrt(3) * np.ones(num_buses)
    V_max = 1.05 * 4.8 / np.sqrt(3) * np.ones(num_buses)

    V_base = 4.8 / np.sqrt(3)  # phase-to-neutral base
    P0_set = load_p0_set_mat("P0_set.mat")

    alpha = 0.05
    nu = 1e-3
    epsilon = 1e-6
    E = 0.001
    cp, cq = 3.0, 1.0

    gamma_n = np.zeros(num_buses)
    mu_n = np.zeros(num_buses)
    lamda = np.zeros(num_buses)
    csi = np.zeros(num_buses)

    G_busnums = [4,7,10,13,17,20,22,23,26,28,29,30,31,32,33,34,35,36]
    G = np.array(G_busnums) - 1

    P_av = np.zeros(num_buses)
    S_av = np.zeros(num_buses)
    P_av[G] = 110.0
    S_av[G] = 200.0
    S_av[9] = 300.0
    S_av[32] = 900.0
    S_av[33] = 900.0

    # --------------------------------------------------------
    # OpenDSS setup
    # --------------------------------------------------------
    Y, _ = d.get_Ymatrix(show_y=False, phase="A")

    d.run_command("Clear")
    d.run_command("Compile ieee37.dss")
    d.run_command("Solve mode=snap")
    d.run_command("Set mode=daily stepsize=1s number=1")

    y_prime = np.zeros(num_buses, dtype=complex)
    y_prime[0] = complex(2475.093067, -8814.828164)

    num_pts = 24 * 3600

    start_ctrl = 12 * 3600
    end_ctrl   = 14 * 3600

    V_allbus = np.zeros((num_buses, num_pts), dtype=complex)
    P0 = np.zeros(num_pts)
    control_signal = False

    # ========================================================
    # Control loop
    # ========================================================
    for present_step in range(num_pts):

        h = 1 if (start_ctrl < present_step <= end_ctrl) else 0

        # Voltages (phase A, kV)
        V_hat = d.get_allbus_phase1_complex_kv()

        # Nominal voltage (previous step)
        if present_step < 2:
            V_nom = V_hat.copy()
        else:
            V_nom = V_allbus[:, present_step - 1]

        # Feeder head active power
        P0_hat, _ = d.get_circuit_power()  # DO NOT flip here

        # Slack/source voltage
        V0 = d.get_v0_from_first_element()

        inj = np.conj(Y) @ np.conj(V_nom) + np.conj(y_prime) * np.conj(V0)
        S_nom = V_nom * inj

        gamma = np.diag(inj)
        Csi = np.diag(V_nom) @ np.conj(Y)

        H11 = np.real(gamma) + np.real(Csi)
        H12 = -np.imag(gamma) + np.imag(Csi)
        H21 = np.imag(gamma) + np.imag(Csi)
        H22 = np.real(gamma) - np.real(Csi)

        H = np.linalg.inv(np.block([[H11, H12],
                                    [H21, H22]]))

        ang = np.angle(S_nom)
        theta_nom = np.hstack([
            np.diag(np.cos(ang)),
            np.diag(np.sin(ang))
        ])

        AB = theta_nom @ H
        A = AB[:, :num_buses]
        B = AB[:, num_buses:]

        g01 = abs(np.real(Y[0, 1]))
        b01 = abs(np.imag(Y[0, 1]))
        theta0 = np.angle(V0)

        psi1 = abs(V0) * (np.cos(theta0) * g01 + np.sin(theta0) * b01)
        psi2 = abs(V0) * (np.cos(theta0) * b01 + np.sin(theta0) * g01)

        left4x4 = np.array([
            [-psi1, 0, psi1, 0],
            [psi2, 0, psi1, 0],
            [0, -psi1, 0, psi2],
            [0, psi2, 0, psi1]
        ])

        Hslice = np.vstack([
            H[0, :num_buses],
            H[0, num_buses:],
            H[1, :num_buses],
            H[1, num_buses:]
        ])

        MN = left4x4 @ Hslice
        M = MN[0:2, :]
        N = MN[2:4, :]

        Pi_hat = np.zeros(num_buses)
        Qi_hat = np.zeros(num_buses)

        for bus in G_busnums:
            p, q = d.get_power(f"PV{bus}", element="Generator", total=True)
            Pi_hat[bus - 1] = p
            Qi_hat[bus - 1] = q

        gamma_new = gamma_n + alpha * (V_min - np.abs(V_hat) - epsilon * gamma_n)
        mu_new = mu_n + alpha * (np.abs(V_hat) - V_max - epsilon * mu_n)

        if h == 1:
            lamda_new = lamda + alpha * (P0_hat - P0_set[present_step] - E - epsilon * lamda)
            csi_new = csi + alpha * (P0_set[present_step] - P0_hat - E - epsilon * csi)
        else:
            lamda_new = lamda.copy()
            csi_new = csi.copy()

        dual = -gamma_new + mu_new

        sum_gn_P = 0.0
        sum_gn_Q = 0.0
        for i in range(num_buses):
            sum_gn_P += A[i, :] @ dual
            sum_gn_Q += B[i, :] @ dual

        grad_P = (
                2 * cp * (Pi_hat - P_av)
                + sum_gn_P
                + h * (lamda_new - csi_new) * M[0, :]
                + nu * Pi_hat
        )

        grad_Q = (
                2 * cq * Qi_hat
                + sum_gn_Q
                + h * (lamda_new - csi_new) * N[0, :]
                + nu * Qi_hat
        )

        mask = np.zeros(num_buses, dtype=bool)
        mask[G] = True
        grad_P[~mask] = 0.0
        grad_Q[~mask] = 0.0

        Pi_next = Pi_hat - alpha * grad_P
        Qi_next = Qi_hat - alpha * grad_Q

        Pi_next, Qi_next = projection_matlab(Pi_next, Qi_next, S_av, P_av)

        if h == 1 and control_signal:
            for bus in G_busnums:
                d.set_power(
                    name=f"PV{bus}",
                    p=float(-Pi_next[bus - 1]), #opendss need positive p, q
                    q=float(-Qi_next[bus - 1]),
                    element="Generator"
                )

        d.run_dss()

        P0[present_step] = d.get_circuit_power()[0]
        V_allbus[:, present_step] = d.get_allbus_phase1_complex_kv()

        if present_step == 12*60*60:

            plotter = LivePlotter(
                P0_set=P0_set,
                V_base=V_base,
                bus_idx=35,  # bus 36
                update_every=10  # every 10 seconds
            )

        if h == 1:
            plotter.update(present_step, P0, V_allbus)

        gamma_n, mu_n, lamda, csi = gamma_new, mu_new, lamda_new, csi_new

        # print("P0_hat:", P0_hat)
        # print("P0_set:", P0_set[present_step])
        # print("sum_gn_P:", sum_gn_P)
        # print("lamda-csi:", lamda_new - csi_new)

        if present_step % 3600 == 0:
            print(f"Hour {present_step//3600}")

    err = mean_square_error(P0, P0_set)
    print("MSE:", err)

    np.save("P0.npy", P0)
    np.save("V_allbus.npy", V_allbus)

if __name__ == "__main__":
    run()

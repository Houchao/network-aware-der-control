# live_plotter.py
import numpy as np
import matplotlib.pyplot as plt


class LivePlotter:
    """
    Live plotting utility for:
      - Feeder head power P0 vs P0_set
      - Voltage magnitude (pu) at a selected bus

    This class is intentionally dumb:
      - No OpenDSS dependency
      - No control logic
      - No side effects outside matplotlib
    """

    def __init__(
        self,
        P0_set,
        V_base,
        bus_idx=19,
        update_every=5
    ):
        """
        Parameters
        ----------
        P0_set : array-like
            Reference feeder power profile
        V_base : float
            Base voltage for pu conversion
        bus_idx : int
            0-based bus index to monitor (default: bus 36)
        update_every : int
            Update plot every N time steps
        """
        self.P0_set = P0_set
        self.V_base = V_base
        self.bus_idx = bus_idx
        self.update_every = update_every

        self._init_figure()

    def _init_figure(self):
        plt.ion()

        self.fig, (self.axP, self.axV) = plt.subplots(
            2, 1, figsize=(10, 6), sharex=True
        )

        # ---- P0 plot ----
        self.line_P0, = self.axP.plot(
            [], [], lw=2, label="P0 (controlled)"
        )
        self.line_P0ref, = self.axP.plot(
            [], [], "--", lw=2, label="P0_set"
        )

        self.axP.set_ylabel("Power (kW)")
        self.axP.legend()
        self.axP.grid(True)

        # ---- Voltage plot ----
        self.line_V, = self.axV.plot(
            [], [], lw=2, label=f"|V| bus {self.bus_idx + 1}"
        )

        self.axV.axhline(1.05, color="r", ls="--", lw=1, alpha=0.7)
        self.axV.axhline(1.00, color="k", ls=":", lw=1, alpha=0.7)

        self.axV.set_ylabel("Voltage (pu)")
        self.axV.set_xlabel("Time (s)")
        self.axV.legend()
        self.axV.grid(True)

        plt.tight_layout()

    def update(self, step, P0, V_allbus):
        """
        Update live plot.

        Parameters
        ----------
        step : int
            Current time step (seconds)
        P0 : ndarray
            Feeder power history
        V_allbus : ndarray
            Complex bus voltages [num_buses, time]
        """
        if step % self.update_every != 0:
            return

        t = np.arange(step + 1)

        # ---- P0 ----
        self.line_P0.set_data(t, P0[:step + 1])
        self.line_P0ref.set_data(t, self.P0_set[:step + 1])

        self.axP.relim()
        self.axP.autoscale_view()

        # ---- Voltage ----
        v_pu = np.abs(V_allbus[self.bus_idx, :step + 1]) / self.V_base
        self.line_V.set_data(t, v_pu)

        self.axV.relim()
        self.axV.autoscale_view()

        plt.pause(0.001)

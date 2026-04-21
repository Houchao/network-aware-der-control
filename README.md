# Network-Aware Evaluation of Distributed Energy Resource Control in Smart Distribution Systems

This repository contains the simulation framework for the paper:

> **A Network-Aware Evaluation of Distributed Energy Resource Control in Smart Distribution Systems**  
> Houchao Gan, Department of Computer Science, City University of New York

---

## Overview

Modern power grids integrate large numbers of Distributed Energy Resources (DERs) — including rooftop solar panels, batteries, and controllable loads — that must be coordinated in real time to maintain grid stability. Most existing DER control studies assume perfect, instantaneous communication between the grid controller and individual DERs. This project challenges that assumption.

This work evaluates a representative Virtual Power Plant (VPP) dispatch algorithm under realistic communication conditions, using a two-stage sequential simulation framework:

- **Stage 1 (Linux):** An ns-3 packet-level network simulation generates realistic downlink delay traces for each DER over a 24-hour window
- **Stage 2 (Windows):** A Python-based power system simulation uses OpenDSS to run the primal-dual VPP dispatch on a modified IEEE 37-node feeder, with the ns-3 delay traces applied to determine which dual-variable updates are received or dropped at each control step

The results demonstrate that communication delays — even moderate ones — can cause significant oscillations in feeder-head power tracking and frequent voltage limit violations, revealing a critical gap in how DER control algorithms are typically evaluated.

---

## Motivation

As renewable energy penetration grows and the grid becomes increasingly decentralized, the interaction between communication infrastructure and distributed control becomes a practical concern for grid reliability and resilience. This framework provides an implementation-driven evaluation that explicitly incorporates network dynamics, offering a more realistic assessment of DER control performance in the field.

This research is part of a broader effort to develop integrated frameworks combining visual data analysis, system simulation, and distributed control to strengthen power grid resilience — including during emergencies and disaster response.

---

## Key Contributions

- A two-stage sequential simulation framework coupling ns-3 network emulation with OpenDSS power system simulation
- Evaluation of a primal-dual VPP dispatch algorithm under both ideal and realistic downlink delay conditions
- A hold-last-value rollback strategy: when a DER does not receive a dual-variable update within a control step, it reuses the last successfully received values
- Demonstration that communication delays cause pronounced oscillations in feeder-head power and voltage limit excursions

---

## Repository Structure

```
├── stage1_ns3/                  # Stage 1: ns-3 network simulation (Linux)
│   └── downlink_delay.cc          # ns-3 script generating per-DER delay traces
│                                # Output: der_downlink_delay.csv
│
├── stage2_opendss/              # Stage 2: Power system simulation (Windows)
│   ├── vpp_*.py                  # VPP dispatch + OpenDSS
│   ├── opendss_wrapper.py       # OpenDSS Python interface
│   └── live_plotter.py          # Optional real-time plotting
│
├── data/                        # Input data
│   ├── ieee37.dss               # Modified IEEE 37-node feeder model
│   ├── P0_set.mat               # Feeder-head active power reference trajectory
│   ├── nrel_irradiance         # Solar irradiance data from NREL MIDC (Aug 15, 2004)
│   └── epri_loads              # EPRI load profiles for IEEE 37-node feeder
│
│
└── README.md
```

---

## Requirements

### Stage 1 — ns-3 (Linux)
- ns-3 (version 3.35 or later)
- See [ns-3 installation guide](https://www.nsnam.org/wiki/Installation)

### Stage 2 — Python + OpenDSS (Windows)
- Python 3.10
- OpenDSS (install from [OpenDSS official site](https://www.epri.com/pages/sa/opendss))
- Python packages:

```bash
pip install numpy scipy matplotlib pandas
```

---

## Usage

### Stage 1: Generate downlink delay traces (Linux)

```bash
cd stage1_ns3
./waf --run downlink_sim
```

This produces `der_downlink_delay.csv` with the format:

```
rx_time_sec, der_id, delay_ms
```

Copy this file to the `stage2_opendss/` directory before running Stage 2.

### Stage 2: Run power system simulation (Windows)

**Ideal communication (no delay):**

```bash
python vpp_clean.py
```

**Realistic downlink delay:**

```bash
python vpp_live_ns_3_dual_delay.py
```


---

## Simulation Parameters

| Parameter | Value |
|-----------|-------|
| Feeder | Modified IEEE 37-node |
| Number of PV systems | 18 |
| PV buses | 4, 7, 10, 13, 17, 20, 22, 23, 26, 28, 29, 30, 31, 32, 33, 34, 35, 36 |
| Control interval | 1 second |
| Simulation duration | 24 hours |
| Control active window | 12:00–14:00 |
| Voltage limits | [0.95, 1.05] p.u. |
| Downlink jitter | U(1 ms, 150 ms) per DER |
| Delay drop threshold | 50 ms (packets above threshold treated as lost) |
| Link data rate | 10 Mb/s |
| Step size α | 0.05 |

---

## How the Delay Model Works

The ns-3 simulation assigns each DER an independent per-packet jitter drawn from U(1 ms, 150 ms). The resulting delay traces are loaded into the Python control loop via `load_downlink_delay_csv()`, which produces a boolean `lost_mask` array of shape `(num_der, num_steps)`.

At each control step, if `lost_mask[j, k]` is `True` for DER `j`, the hold-last-value strategy is applied: the dual variables for that DER are rolled back to their previous values rather than updated. This directly models the effect of a dropped or late-arriving coordination packet on closed-loop control behavior.

---

## Results Summary

| Condition | Feeder-Head Tracking | Voltage Regulation |
|-----------|---------------------|-------------------|
| Ideal communication | Close tracking, stable | Within [0.95, 1.05] p.u. |
| Realistic downlink delay | Large oscillations | Frequent limit violations |

---

## Data Sources

Solar irradiance data is obtained from the **National Renewable Energy Laboratory (NREL) Measurement and Instrumentation Data Center (MIDC)**, August 15, 2004. Load profiles are based on EPRI datasets for Sacramento, CA (August 15, 2001).

---

## Future Work

- Add uplink delay modeling and shared-media contention in ns-3
- Extend to heterogeneous DER portfolios and nonlinear AC power flow
- Implement delay-aware and event-triggered control schemes
- Integrate with 3D reconstruction and visual damage assessment pipelines for disaster response scenarios

---

## Citation

If you use this code in your research, please cite:

```bibtex
@article{gan2025network,
  title={A Network-Aware Evaluation of Distributed Energy Resource Control in Smart Distribution Systems},
  author={Gan, Houchao},
  institution={City University of New York},
  year={2025}
}
```

---

## License

This project is released under the MIT License.

---

## Contact

Houchao Gan  
Department of Computer Science, City University of New York  
hgan@gradcenter.cuny.edu

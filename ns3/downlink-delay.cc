#include "ns3/core-module.h"
#include "ns3/network-module.h"
#include "ns3/internet-module.h"
#include "ns3/point-to-point-module.h"
#include "ns3/applications-module.h"
#include "ns3/timestamp-tag.h"

#include <fstream>
#include <vector>
#include <sstream>

using namespace ns3;

// ---------- Global log ----------
static std::ofstream g_log;

// ---------- One jitter RV per DER (1..N) ----------
static std::vector< Ptr<UniformRandomVariable> > g_jitter; // index 1..N

// ---------- Tx: stamp packet with send time ----------
static void
TxTrace (uint32_t derId, Ptr<const Packet> pkt)
{
    // Add timestamp tag directly to the packet about to be sent.
    // (Yes, const_cast is common in ns-3 tracing for packet annotation.)
    Ptr<Packet> p = const_cast<Packet*> (PeekPointer (pkt));

    TimestampTag tag;
    tag.SetTimestamp (Simulator::Now ());
    p->AddPacketTag (tag);

    (void)derId; // derId not needed here, but kept for symmetry/debug
}

// ---------- Delayed logging after extra jitter ----------
static void
DelayedLog (uint32_t derId, Ptr<const Packet> pkt)
{
    Ptr<Packet> copy = pkt->Copy ();

    TimestampTag tag;
    if (!copy->PeekPacketTag (tag))
    {
        return; // no tag -> skip
    }

    Time tx = tag.GetTimestamp ();
    Time rx = Simulator::Now ();
    double delayMs = (rx - tx).GetMilliSeconds ();

    // CSV: rx_time_sec,der_id,delay_ms
    g_log << rx.GetSeconds ()
          << "," << derId
          << "," << delayMs
          << std::endl;
}

// ---------- Rx: add extra per-DER random delay, then log ----------
static void
RxTrace (uint32_t derId, Ptr<const Packet> pkt, const Address &from)
{
    (void)from;

    // extra jitter per DER (independent)
    Ptr<UniformRandomVariable> rv = g_jitter.at (derId); // derId in [1..N]
    double extraSec = rv->GetValue (); // seconds

    Simulator::Schedule (Seconds (extraSec), &DelayedLog, derId, pkt);
}

int
main (int argc, char *argv[])
{
    uint32_t N_DER = 18;
    double simTime = 86400.0;     // default: 24h
    double sendInterval = 1.0;    // 1 packet / second
    double linkDelayMs = 1.0;     // fixed propagation delay on each link

    // extra random delay per DER (seconds)
    double jitterMinMs = 1.0;
    double jitterMaxMs = 150.0;

    uint16_t basePort = 9000;
    std::string outCsv = "der_downlink_delay.csv";

    CommandLine cmd;
    cmd.AddValue ("N_DER", "Number of DER nodes", N_DER);
    cmd.AddValue ("simTime", "Simulation time (seconds)", simTime);
    cmd.AddValue ("sendInterval", "UDP send interval (seconds)", sendInterval);
    cmd.AddValue ("linkDelayMs", "Fixed p2p link propagation delay (ms)", linkDelayMs);
    cmd.AddValue ("jitterMinMs", "Extra per-DER jitter min (ms)", jitterMinMs);
    cmd.AddValue ("jitterMaxMs", "Extra per-DER jitter max (ms)", jitterMaxMs);
    cmd.AddValue ("outCsv", "Output CSV filename", outCsv);
    cmd.Parse (argc, argv);

    // Open CSV log
    g_log.open (outCsv, std::ios::out | std::ios::trunc);
    if (!g_log.is_open ())
    {
        NS_FATAL_ERROR ("Cannot open output file: " << outCsv);
    }

    // Nodes
    NodeContainer controller;
    controller.Create (1);

    NodeContainer ders;
    ders.Create (N_DER);

    // Internet stack
    InternetStackHelper internet;
    internet.Install (controller);
    internet.Install (ders);

    // Prepare per-DER jitter RVs (index 0 unused; use 1..N)
    g_jitter.assign (N_DER + 1, nullptr);
    for (uint32_t i = 1; i <= N_DER; ++i)
    {
        Ptr<UniformRandomVariable> rv = CreateObject<UniformRandomVariable> ();
        rv->SetAttribute ("Min", DoubleValue (jitterMinMs / 1000.0));
        rv->SetAttribute ("Max", DoubleValue (jitterMaxMs / 1000.0));
        rv->SetStream (1000 + i); // stable per-DER independence
        g_jitter[i] = rv;
    }

    // Build independent links: controller <-> DER_i
    for (uint32_t i = 0; i < N_DER; ++i)
    {
        uint32_t derId = i + 1;

        PointToPointHelper p2p;
        p2p.SetDeviceAttribute ("DataRate", StringValue ("10Mbps"));
        p2p.SetChannelAttribute ("Delay", TimeValue (MilliSeconds (linkDelayMs)));

        NodeContainer pair (controller.Get (0), ders.Get (i));
        NetDeviceContainer devices = p2p.Install (pair);

        // Assign a unique /24 subnet per DER link
        Ipv4AddressHelper ipv4;
        std::ostringstream subnet;
        subnet << "10.1." << derId << ".0";
        ipv4.SetBase (subnet.str ().c_str (), "255.255.255.0");
        Ipv4InterfaceContainer interfaces = ipv4.Assign (devices);

        // DER-side UDP server
        UdpServerHelper server (basePort + i);
        ApplicationContainer serverApp = server.Install (ders.Get (i));
        serverApp.Start (Seconds (0.0));
        serverApp.Stop (Seconds (simTime));

        // Controller-side UDP client -> this DER
        UdpClientHelper client (interfaces.GetAddress (1), basePort + i);
        client.SetAttribute ("Interval", TimeValue (Seconds (sendInterval)));
        client.SetAttribute ("PacketSize", UintegerValue (64));
        client.SetAttribute ("MaxPackets", UintegerValue (uint32_t (simTime / sendInterval) + 10));

        ApplicationContainer clientApp = client.Install (controller.Get (0));
        clientApp.Start (Seconds (1.0));
        clientApp.Stop (Seconds (simTime));

        // ---- Traces ----
        // Stamp at Tx (client)
        clientApp.Get (0)->TraceConnectWithoutContext (
            "Tx",
            MakeBoundCallback (&TxTrace, derId)
        );

        // Log at Rx with extra random delay (server)
        serverApp.Get (0)->TraceConnectWithoutContext (
            "Rx",
            MakeBoundCallback (&RxTrace, derId)
        );
    }

    Ipv4GlobalRoutingHelper::PopulateRoutingTables ();

    Simulator::Stop (Seconds (simTime));
    Simulator::Run ();
    Simulator::Destroy ();

    g_log.close ();
    return 0;
}

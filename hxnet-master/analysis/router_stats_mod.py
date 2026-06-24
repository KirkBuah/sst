"""
SST statistics module (loaded via emberLoad.py's --statsModule hook) that turns on
the per-port router statistics merlin.hr_router already documents:

    send_packet_count   - packets sent on each output port   (hr_router.h:76)
    send_bit_count      - bits sent on each output port       (hr_router.h:75)
    output_port_stalls  - time each output port is stalled    (hr_router.h:77)

Each is registered per output port with subId "portN" (hr_router.cc:264-272), so
the resulting CSV has one row per (router, port) per statistic -- exactly what the
load-imbalance diagnosis needs.

emberLoad.py does `import <module>; module.init(statsFile)`; pass
`--statsModule=router_stats_mod --statsFile=<path.csv>` in --model-options and make
sure this file's directory is on PYTHONPATH (router_load_diag.py adds analysis/).
"""

import sst

# AccumulatorStatistic + rate 0ns -> one final accumulated value per port at the
# end of the run (totals over the whole simulation), which is what we aggregate.
#
# NOTE: enabling the three stats individually with enableStatisticForComponentType
# triggers an SST 11.1.0 statOutputCSV bug where many rows are written with a BLANK
# StatisticName/StatisticSubId (so ports cannot be identified and totals are wrong).
# enableAllStatisticsForComponentType labels every (component, port) row correctly;
# router_load_diag.py filters by StatisticName, so the extra stats are harmless.
_ACC = {"type": "sst.AccumulatorStatistic", "rate": "0ns"}


def init(outputFile):
    sst.setStatisticLoadLevel(9)
    sst.setStatisticOutput("sst.statOutputCSV")
    sst.setStatisticOutputOptions({
        "filepath": outputFile,
        "separator": ", ",
    })
    sst.enableAllStatisticsForComponentType("merlin.hr_router", _ACC)

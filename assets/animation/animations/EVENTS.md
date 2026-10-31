# 动画事件表

`time` / `time_seconds` 的单位均为秒；`frame_index` 从 0 开始，为首个采样时刻不早于事件的帧。运动曲线 key 使用归一化相位，两者不要混用。

| 序列 | 事件 | 秒 | 归一化相位 | 帧（0 基） | 采样秒 |
|---|---|---:|---:|---:|---:|
| `attack` | `impact` | 0.540 | 0.540000 | 13 | 0.541667 |
| `attack` | `recover` | 0.720 | 0.720000 | 18 | 0.750000 |
| `attack_heavy` | `impact` | 0.800 | 0.600000 | 20 | 0.833333 |
| `attack_heavy` | `recover` | 1.020 | 0.765000 | 25 | 1.041667 |
| `bite` | `impact` | 0.530 | 0.530000 | 13 | 0.541667 |
| `bite` | `recover` | 0.720 | 0.720000 | 18 | 0.750000 |
| `cast` | `cast_release` | 0.900 | 0.600000 | 22 | 0.916667 |
| `cast` | `recover` | 1.200 | 0.800000 | 29 | 1.208333 |
| `hurt` | `hurt_recoil` | 0.120 | 0.180000 | 3 | 0.125000 |
| `hurt` | `recover` | 0.400 | 0.600000 | 10 | 0.416667 |
| `block` | `guard_on` | 0.280 | 0.280000 | 7 | 0.291667 |
| `block` | `blocked_impact` | 0.480 | 0.480000 | 12 | 0.500000 |
| `block` | `guard_off` | 0.740 | 0.740000 | 18 | 0.750000 |
| `counter` | `guard_on` | 0.350 | 0.262500 | 9 | 0.375000 |
| `counter` | `absorbed_impact` | 0.520 | 0.390000 | 13 | 0.541667 |
| `counter` | `counter_impact` | 0.840 | 0.630000 | 21 | 0.875000 |
| `counter` | `recover` | 1.080 | 0.810000 | 26 | 1.083333 |
| `domain_enter` | `domain_on` | 0.880 | 0.480000 | 22 | 0.916667 |
| `domain_enter` | `recover` | 1.500 | 0.818182 | 36 | 1.500000 |
| `domain_exit` | `domain_off` | 0.900 | 0.600000 | 22 | 0.916667 |
| `domain_exit` | `recover` | 1.250 | 0.833333 | 30 | 1.250000 |
| `feral_enter` | `feral_on` | 0.920 | 0.613333 | 23 | 0.958333 |
| `feral_enter` | `recover` | 1.250 | 0.833333 | 30 | 1.250000 |
| `die` | `body_ground_impact` | 1.220 | 0.732000 | 30 | 1.250000 |
| `die` | `dead` | 1.600 | 0.960000 | 39 | 1.625000 |
| `domain_attack` | `impact` | 0.540 | 0.540000 | 13 | 0.541667 |
| `domain_attack` | `recover` | 0.720 | 0.720000 | 18 | 0.750000 |
| `domain_cast` | `cast_release` | 0.900 | 0.600000 | 22 | 0.916667 |
| `domain_cast` | `recover` | 1.200 | 0.800000 | 29 | 1.208333 |
| `domain_hurt` | `hurt_recoil` | 0.120 | 0.180000 | 3 | 0.125000 |
| `domain_hurt` | `recover` | 0.400 | 0.600000 | 10 | 0.416667 |
| `domain_block` | `guard_on` | 0.280 | 0.280000 | 7 | 0.291667 |
| `domain_block` | `blocked_impact` | 0.480 | 0.480000 | 12 | 0.500000 |
| `domain_block` | `guard_off` | 0.740 | 0.740000 | 18 | 0.750000 |
| `domain_die` | `body_ground_impact` | 1.220 | 0.732000 | 30 | 1.250000 |
| `domain_die` | `dead` | 1.600 | 0.960000 | 39 | 1.625000 |
| `domain_die` | `domain_off` | 1.120 | 0.672000 | 27 | 1.125000 |
| `roar` | `roar_release` | 0.520 | 0.346667 | 13 | 0.541667 |
| `roar` | `roar_peak` | 0.980 | 0.653333 | 24 | 1.000000 |
| `roar` | `recover` | 1.250 | 0.833333 | 30 | 1.250000 |
| `storm_leap` | `takeoff` | 0.460 | 0.230000 | 12 | 0.500000 |
| `storm_leap` | `apex` | 0.920 | 0.460000 | 23 | 0.958333 |
| `storm_leap` | `landing_impact` | 1.440 | 0.720000 | 35 | 1.458333 |
| `storm_leap` | `aftershock` | 1.630 | 0.815000 | 40 | 1.666667 |
| `storm_leap` | `recover` | 1.800 | 0.900000 | 44 | 1.833333 |
| `domain_roar` | `roar_release` | 0.520 | 0.346667 | 13 | 0.541667 |
| `domain_roar` | `roar_peak` | 0.980 | 0.653333 | 24 | 1.000000 |
| `domain_roar` | `recover` | 1.250 | 0.833333 | 30 | 1.250000 |
| `domain_storm_leap` | `takeoff` | 0.460 | 0.230000 | 12 | 0.500000 |
| `domain_storm_leap` | `apex` | 0.920 | 0.460000 | 23 | 0.958333 |
| `domain_storm_leap` | `landing_impact` | 1.440 | 0.720000 | 35 | 1.458333 |
| `domain_storm_leap` | `aftershock` | 1.630 | 0.815000 | 40 | 1.666667 |
| `domain_storm_leap` | `recover` | 1.800 | 0.900000 | 44 | 1.833333 |

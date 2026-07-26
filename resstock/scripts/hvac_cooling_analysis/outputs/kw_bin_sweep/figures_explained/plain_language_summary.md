# Plain-language interpretation of the kW-bin sweep

The sweep tests different ways to group cooling devices by observed electrical kW.

A good binning scheme should do two things:

1. Put electrically similar devices in the same bin.
2. Keep enough devices in each bin so small transformer groups can be represented.

The best scheme in the current sweep is `pooled_quantile_8_bins`.

Its bin labels are:

```text
0-0.6127 | 0.6127-0.8168 | 0.8168-1.0127 | 1.0127-1.257 | 1.257-1.5372 | 1.5372-1.8822 | 1.8822-2.4191 | 2.4191+
```

This is a pooled quantile scheme. That means all active cooling devices from up00, up01, and up02 were pooled together, sorted by observed peak kW, and split into eight similarly populated groups.

The bin edges look unusual because they come from the data distribution, not from manually chosen round numbers.

Prediction error for the best scheme by transformer group size:

```text
 2 devices: median error = 3.78%, p90 error = 10.49%
 3 devices: median error = 3.04%, p90 error = 8.49%
 4 devices: median error = 2.57%, p90 error = 7.77%
 5 devices: median error = 2.31%, p90 error = 6.97%
 6 devices: median error = 2.13%, p90 error = 6.39%
 8 devices: median error = 1.81%, p90 error = 5.69%
10 devices: median error = 1.60%, p90 error = 5.28%
13 devices: median error = 1.49%, p90 error = 5.03%
```

The most important figure is `03_prediction_error_vs_group_size.png` because it directly connects the binning method to the transformer problem.

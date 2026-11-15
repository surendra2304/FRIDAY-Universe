# RD-006 analysis digest
synthesis verdict counts: {'FAIL': 261, 'INSUFFICIENT': 148}
configs with trades: 409
cross-trial Sharpe var: 0.017525

## Screen funnel per tf x fold (W1-W5 only)
1h W1: screened=435 data_skip=0 adf_pass=37 selected=12 trade_data_skip=0
1h W2: screened=435 data_skip=0 adf_pass=55 selected=32 trade_data_skip=0
1h W3: screened=435 data_skip=0 adf_pass=44 selected=36 trade_data_skip=0
1h W4: screened=435 data_skip=0 adf_pass=26 selected=16 trade_data_skip=0
1h W5: screened=435 data_skip=0 adf_pass=34 selected=16 trade_data_skip=0
4h W1: screened=435 data_skip=0 adf_pass=28 selected=28 trade_data_skip=0
4h W2: screened=435 data_skip=0 adf_pass=37 selected=37 trade_data_skip=0
4h W3: screened=435 data_skip=0 adf_pass=41 selected=41 trade_data_skip=0
4h W4: screened=435 data_skip=0 adf_pass=19 selected=19 trade_data_skip=0
4h W5: screened=435 data_skip=0 adf_pass=27 selected=27 trade_data_skip=0

## Selection persistence (per pair, per tf): # folds selected
selected in 0 folds: 657 pair-tf combos
selected in 1 folds: 170 pair-tf combos
selected in 2 folds: 36 pair-tf combos
selected in 3 folds: 6 pair-tf combos
selected in 4 folds: 1 pair-tf combos
pairs selected in >=3 folds: 7

## Cointegration breakdown: selected early (W1/W2), screen-fails later
count: 99
  ADAUSDT/ALGOUSDT 1h
  ADAUSDT/ALGOUSDT 4h
  ADAUSDT/DOTUSDT 4h
  ADAUSDT/XLMUSDT 4h
  ALGOUSDT/MANAUSDT 1h
  ALGOUSDT/MANAUSDT 4h
  ALGOUSDT/SANDUSDT 1h
  ALGOUSDT/SANDUSDT 4h
  APTUSDT/ALGOUSDT 4h
  APTUSDT/MANAUSDT 1h
  APTUSDT/MANAUSDT 4h
  APTUSDT/SANDUSDT 1h
  APTUSDT/SANDUSDT 4h
  ATOMUSDT/MANAUSDT 1h
  ATOMUSDT/MANAUSDT 4h
  ATOMUSDT/SANDUSDT 1h
  ATOMUSDT/SANDUSDT 4h
  AVAXUSDT/ALGOUSDT 1h
  AVAXUSDT/ALGOUSDT 4h
  DOGEUSDT/BCHUSDT 1h
  DOGEUSDT/BCHUSDT 4h
  DOTUSDT/ALGOUSDT 1h
  DOTUSDT/ALGOUSDT 4h
  DOTUSDT/APTUSDT 1h
  DOTUSDT/APTUSDT 4h
  DOTUSDT/ATOMUSDT 4h
  DOTUSDT/AVAXUSDT 4h
  DOTUSDT/OPUSDT 4h
  DOTUSDT/SANDUSDT 4h
  ETCUSDT/HBARUSDT 4h
  FILUSDT/ALGOUSDT 1h
  FILUSDT/ALGOUSDT 4h
  FILUSDT/APTUSDT 1h
  FILUSDT/APTUSDT 4h
  FILUSDT/HBARUSDT 4h
  FILUSDT/MANAUSDT 1h
  FILUSDT/VETUSDT 4h
  HBARUSDT/VETUSDT 1h
  HBARUSDT/VETUSDT 4h
  INJUSDT/MANAUSDT 4h

## Traded-fold sign flips: positive fold then negative fold (same config)
count: 28
  ('ADAUSDT/XLMUSDT', '1h', 2.0, {'W3': 0.1245, 'W4': -0.9913})
  ('ADAUSDT/XLMUSDT', '1h', 2.5, {'W3': 0.0129, 'W4': -1.1126})
  ('BNBUSDT/AAVEUSDT', '1h', 2.5, {'W3': 0.0254, 'W4': -4.5128})
  ('BNBUSDT/AAVEUSDT', '4h', 2.5, {'W3': 0.0226, 'W4': -1.3527})
  ('BNBUSDT/SUIUSDT', '1h', 2.0, {'W3': 0.2125, 'W4': -5.1229})
  ('BNBUSDT/SUIUSDT', '4h', 2.0, {'W3': 0.1918, 'W4': -1.2697})
  ('BNBUSDT/TRXUSDT', '1h', 2.0, {'W3': 0.2316, 'W4': -3.6618})
  ('BNBUSDT/TRXUSDT', '1h', 2.5, {'W3': 0.3351, 'W4': -3.6096})
  ('BNBUSDT/TRXUSDT', '4h', 2.0, {'W3': 0.2224, 'W4': -0.8545})
  ('BNBUSDT/TRXUSDT', '4h', 2.5, {'W3': 0.3253, 'W4': -0.7958})
  ('BNBUSDT/XLMUSDT', '1h', 2.0, {'W3': 0.2028, 'W4': -4.4583})
  ('BNBUSDT/XLMUSDT', '1h', 2.5, {'W3': 0.3087, 'W4': -4.4066})
  ('BNBUSDT/XLMUSDT', '4h', 2.0, {'W3': 0.2579, 'W4': -1.0608})
  ('BNBUSDT/XLMUSDT', '4h', 2.5, {'W3': 0.2871, 'W4': -1.0143})
  ('DOTUSDT/SANDUSDT', '1h', 2.0, {'W4': 0.0914, 'W5': -0.1582})
  ('HBARUSDT/VETUSDT', '4h', 2.0, {'W1': 0.0115, 'W2': -1.4977})
  ('HBARUSDT/VETUSDT', '4h', 2.5, {'W1': 0.0609, 'W2': -1.4977})
  ('LINKUSDT/ALGOUSDT', '1h', 2.0, {'W3': 0.736, 'W4': -1.769})
  ('LINKUSDT/ALGOUSDT', '1h', 2.5, {'W3': 0.6814, 'W4': -1.7193})
  ('LINKUSDT/ALGOUSDT', '4h', 2.0, {'W3': 0.7541, 'W4': -0.2977})
  ('LTCUSDT/ETCUSDT', '4h', 2.0, {'W1': 0.2778, 'W2': -1.4572})
  ('LTCUSDT/UNIUSDT', '4h', 2.0, {'W1': 0.3427, 'W2': -0.8738, 'W5': -0.1701})
  ('LTCUSDT/UNIUSDT', '4h', 2.5, {'W1': 0.4748, 'W2': -0.8738, 'W5': -0.0759})
  ('LTCUSDT/XLMUSDT', '1h', 2.0, {'W4': 0.2328, 'W5': -0.085})
  ('LTCUSDT/XLMUSDT', '4h', 2.0, {'W3': 0.6956, 'W4': 0.2588, 'W5': -0.0824})

## Verdict table (all configs with n>=30, sorted by PF desc)
VETUSDT/SANDUSDT 1h E2.0: n=72 exp=0.01695 PF=3.330 PF2x=2.525 folds=2 foldpos=1.00 p=4.47e-02 DSR=0.000 maxDD=0.337 verdict=FAIL
VETUSDT/SANDUSDT 1h E2.5: n=69 exp=0.01095 PF=2.459 PF2x=1.831 folds=2 foldpos=1.00 p=8.52e-02 DSR=0.000 maxDD=0.337 verdict=FAIL
ADAUSDT/DOTUSDT 4h E2.0: n=30 exp=0.00318 PF=1.537 PF2x=0.998 folds=1 foldpos=1.00 p=2.22e-01 DSR=0.033 maxDD=0.061 verdict=FAIL
NEARUSDT/OPUSDT 4h E2.0: n=73 exp=0.00346 PF=1.361 PF2x=1.023 folds=2 foldpos=1.00 p=2.25e-01 DSR=0.001 maxDD=0.313 verdict=FAIL
LINKUSDT/ALGOUSDT 4h E2.0: n=173 exp=0.00264 PF=1.327 PF2x=0.944 folds=2 foldpos=0.50 p=2.67e-01 DSR=0.000 maxDD=0.650 verdict=FAIL
NEARUSDT/OPUSDT 4h E2.5: n=72 exp=0.00211 PF=1.218 PF2x=0.904 folds=1 foldpos=1.00 p=3.16e-01 DSR=0.000 maxDD=0.313 verdict=FAIL
DOTUSDT/ALGOUSDT 4h E2.0: n=59 exp=0.00132 PF=1.152 PF2x=0.826 folds=1 foldpos=1.00 p=4.14e-01 DSR=0.000 maxDD=0.399 verdict=FAIL
DOGEUSDT/BCHUSDT 1h E2.0: n=52 exp=0.00019 PF=1.036 PF2x=0.588 folds=1 foldpos=1.00 p=4.65e-01 DSR=0.001 maxDD=0.078 verdict=FAIL
DOTUSDT/ALGOUSDT 4h E2.5: n=58 exp=0.00014 PF=1.015 PF2x=0.733 folds=1 foldpos=1.00 p=4.91e-01 DSR=0.000 maxDD=0.399 verdict=FAIL
FILUSDT/VETUSDT 4h E2.0: n=183 exp=-0.00007 PF=0.995 PF2x=0.789 folds=2 foldpos=0.50 p=5.05e-01 DSR=0.000 maxDD=1.366 verdict=FAIL
BNBUSDT/ADAUSDT 1h E2.0: n=30 exp=-0.00035 PF=0.965 PF2x=0.715 folds=1 foldpos=0.00 p=5.15e-01 DSR=0.007 maxDD=0.280 verdict=FAIL
ADAUSDT/DOTUSDT 4h E2.5: n=30 exp=-0.00101 PF=0.900 PF2x=0.645 folds=1 foldpos=0.00 p=5.59e-01 DSR=0.004 maxDD=0.061 verdict=FAIL
DOTUSDT/SANDUSDT 1h E2.0: n=40 exp=-0.00167 PF=0.897 PF2x=0.739 folds=2 foldpos=0.50 p=5.57e-01 DSR=0.002 maxDD=0.426 verdict=FAIL
DOGEUSDT/BCHUSDT 1h E2.5: n=52 exp=-0.00063 PF=0.896 PF2x=0.529 folds=1 foldpos=0.00 p=6.08e-01 DSR=0.000 maxDD=0.078 verdict=FAIL
LINKUSDT/ALGOUSDT 4h E2.5: n=171 exp=-0.00142 PF=0.819 PF2x=0.526 folds=1 foldpos=0.00 p=7.14e-01 DSR=0.000 maxDD=0.497 verdict=FAIL
XRPUSDT/AAVEUSDT 4h E2.5: n=392 exp=-0.00212 PF=0.797 PF2x=0.574 folds=1 foldpos=0.00 p=9.46e-01 DSR=0.000 maxDD=1.190 verdict=FAIL
DOTUSDT/ETCUSDT 4h E2.0: n=58 exp=-0.00208 PF=0.794 PF2x=0.559 folds=1 foldpos=0.00 p=6.67e-01 DSR=0.000 maxDD=0.296 verdict=FAIL
XRPUSDT/AAVEUSDT 4h E2.0: n=392 exp=-0.00223 PF=0.789 PF2x=0.569 folds=1 foldpos=0.00 p=9.53e-01 DSR=0.000 maxDD=1.190 verdict=FAIL
NEARUSDT/OPUSDT 1h E2.0: n=286 exp=-0.00138 PF=0.766 PF2x=0.427 folds=2 foldpos=0.50 p=8.82e-01 DSR=0.000 maxDD=0.848 verdict=FAIL
BNBUSDT/TRXUSDT 4h E2.5: n=268 exp=-0.00176 PF=0.760 PF2x=0.481 folds=2 foldpos=0.50 p=8.81e-01 DSR=0.000 maxDD=0.827 verdict=FAIL
LTCUSDT/UNIUSDT 4h E2.5: n=116 exp=-0.00409 PF=0.726 PF2x=0.568 folds=3 foldpos=0.33 p=7.68e-01 DSR=0.000 maxDD=0.950 verdict=FAIL
NEARUSDT/OPUSDT 1h E2.5: n=285 exp=-0.00165 PF=0.721 PF2x=0.395 folds=1 foldpos=0.00 p=9.26e-01 DSR=0.000 maxDD=0.848 verdict=FAIL
BNBUSDT/TRXUSDT 4h E2.0: n=268 exp=-0.00236 PF=0.687 PF2x=0.430 folds=2 foldpos=0.50 p=9.53e-01 DSR=0.000 maxDD=0.886 verdict=FAIL
LINKUSDT/ALGOUSDT 1h E2.0: n=675 exp=-0.00153 PF=0.686 PF2x=0.353 folds=2 foldpos=0.50 p=9.21e-01 DSR=0.000 maxDD=2.178 verdict=FAIL
BNBUSDT/XLMUSDT 4h E2.5: n=330 exp=-0.00220 PF=0.681 PF2x=0.410 folds=2 foldpos=0.50 p=9.66e-01 DSR=0.000 maxDD=1.014 verdict=FAIL
LINKUSDT/ALGOUSDT 1h E2.5: n=674 exp=-0.00154 PF=0.680 PF2x=0.346 folds=2 foldpos=0.50 p=8.98e-01 DSR=0.000 maxDD=2.129 verdict=FAIL
FILUSDT/VETUSDT 4h E2.5: n=180 exp=-0.00442 PF=0.675 PF2x=0.515 folds=1 foldpos=0.00 p=8.86e-01 DSR=0.000 maxDD=1.366 verdict=FAIL
FILUSDT/HBARUSDT 4h E2.0: n=372 exp=-0.00294 PF=0.673 PF2x=0.445 folds=1 foldpos=0.00 p=9.95e-01 DSR=0.000 maxDD=1.357 verdict=FAIL
FILUSDT/HBARUSDT 4h E2.5: n=372 exp=-0.00304 PF=0.662 PF2x=0.436 folds=1 foldpos=0.00 p=9.96e-01 DSR=0.000 maxDD=1.357 verdict=FAIL
DOTUSDT/APTUSDT 4h E2.5: n=129 exp=-0.00294 PF=0.658 PF2x=0.414 folds=2 foldpos=0.50 p=8.93e-01 DSR=0.000 maxDD=0.691 verdict=FAIL
BNBUSDT/XLMUSDT 4h E2.0: n=330 exp=-0.00243 PF=0.655 PF2x=0.395 folds=2 foldpos=0.50 p=9.74e-01 DSR=0.000 maxDD=1.061 verdict=FAIL
AVAXUSDT/ALGOUSDT 4h E2.0: n=354 exp=-0.00399 PF=0.642 PF2x=0.450 folds=2 foldpos=0.00 p=9.94e-01 DSR=0.000 maxDD=1.590 verdict=FAIL
ETCUSDT/FILUSDT 4h E2.5: n=57 exp=-0.00325 PF=0.629 PF2x=0.398 folds=1 foldpos=0.00 p=8.35e-01 DSR=0.000 maxDD=0.116 verdict=FAIL
LTCUSDT/ETCUSDT 4h E2.0: n=330 exp=-0.00357 PF=0.628 PF2x=0.417 folds=2 foldpos=0.50 p=9.84e-01 DSR=0.000 maxDD=1.489 verdict=FAIL
DOTUSDT/ETCUSDT 4h E2.5: n=57 exp=-0.00313 PF=0.620 PF2x=0.375 folds=1 foldpos=0.00 p=9.12e-01 DSR=0.000 maxDD=0.117 verdict=FAIL
FILUSDT/ALGOUSDT 4h E2.0: n=382 exp=-0.00357 PF=0.618 PF2x=0.404 folds=1 foldpos=0.00 p=9.99e-01 DSR=0.000 maxDD=1.509 verdict=FAIL
LTCUSDT/UNIUSDT 4h E2.0: n=116 exp=-0.00605 PF=0.616 PF2x=0.478 folds=3 foldpos=0.33 p=8.88e-01 DSR=0.000 maxDD=1.044 verdict=FAIL
OPUSDT/INJUSDT 4h E2.5: n=66 exp=-0.00625 PF=0.615 PF2x=0.482 folds=1 foldpos=0.00 p=8.52e-01 DSR=0.000 maxDD=0.577 verdict=FAIL
BNBUSDT/SUIUSDT 4h E2.0: n=384 exp=-0.00281 PF=0.611 PF2x=0.369 folds=2 foldpos=0.50 p=9.93e-01 DSR=0.000 maxDD=1.332 verdict=FAIL
HBARUSDT/VETUSDT 4h E2.5: n=350 exp=-0.00411 PF=0.611 PF2x=0.410 folds=2 foldpos=0.50 p=9.95e-01 DSR=0.000 maxDD=1.508 verdict=FAIL
FILUSDT/ALGOUSDT 4h E2.5: n=382 exp=-0.00364 PF=0.611 PF2x=0.399 folds=1 foldpos=0.00 p=9.99e-01 DSR=0.000 maxDD=1.509 verdict=FAIL
DOTUSDT/APTUSDT 4h E2.0: n=129 exp=-0.00342 PF=0.608 PF2x=0.375 folds=2 foldpos=0.50 p=9.33e-01 DSR=0.000 maxDD=0.706 verdict=FAIL
HBARUSDT/VETUSDT 4h E2.0: n=350 exp=-0.00425 PF=0.598 PF2x=0.398 folds=2 foldpos=0.50 p=9.97e-01 DSR=0.000 maxDD=1.508 verdict=FAIL
AVAXUSDT/ALGOUSDT 4h E2.5: n=354 exp=-0.00493 PF=0.589 PF2x=0.416 folds=2 foldpos=0.00 p=9.97e-01 DSR=0.000 maxDD=1.590 verdict=FAIL
BCHUSDT/MANAUSDT 4h E2.0: n=153 exp=-0.00318 PF=0.586 PF2x=0.344 folds=1 foldpos=0.00 p=9.91e-01 DSR=0.000 maxDD=0.530 verdict=FAIL
BNBUSDT/BCHUSDT 4h E2.5: n=193 exp=-0.00281 PF=0.585 PF2x=0.337 folds=1 foldpos=0.00 p=9.91e-01 DSR=0.000 maxDD=0.539 verdict=FAIL
XRPUSDT/NEARUSDT 4h E2.5: n=393 exp=-0.00671 PF=0.582 PF2x=0.451 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=2.338 verdict=FAIL
XRPUSDT/ADAUSDT 4h E2.5: n=392 exp=-0.00443 PF=0.576 PF2x=0.385 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=1.670 verdict=FAIL
BNBUSDT/BCHUSDT 4h E2.0: n=193 exp=-0.00296 PF=0.573 PF2x=0.332 folds=1 foldpos=0.00 p=9.91e-01 DSR=0.000 maxDD=0.539 verdict=FAIL
XRPUSDT/NEARUSDT 4h E2.0: n=393 exp=-0.00698 PF=0.572 PF2x=0.444 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=2.338 verdict=FAIL
ETCUSDT/FILUSDT 4h E2.0: n=57 exp=-0.00431 PF=0.561 PF2x=0.362 folds=1 foldpos=0.00 p=8.45e-01 DSR=0.000 maxDD=0.116 verdict=FAIL
XRPUSDT/ADAUSDT 4h E2.0: n=392 exp=-0.00477 PF=0.557 PF2x=0.375 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=1.670 verdict=FAIL
HBARUSDT/ALGOUSDT 1h E2.5: n=65 exp=-0.00271 PF=0.549 PF2x=0.300 folds=1 foldpos=0.00 p=8.75e-01 DSR=0.000 maxDD=0.321 verdict=FAIL
XRPUSDT/SUIUSDT 4h E2.5: n=393 exp=-0.00600 PF=0.546 PF2x=0.400 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=2.180 verdict=FAIL
LTCUSDT/ETCUSDT 4h E2.5: n=329 exp=-0.00437 PF=0.543 PF2x=0.347 folds=1 foldpos=0.00 p=9.99e-01 DSR=0.000 maxDD=1.164 verdict=FAIL
XRPUSDT/SUIUSDT 4h E2.0: n=393 exp=-0.00612 PF=0.541 PF2x=0.397 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=2.180 verdict=FAIL
XRPUSDT/TRXUSDT 4h E2.5: n=393 exp=-0.00600 PF=0.539 PF2x=0.392 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=2.168 verdict=FAIL
ATOMUSDT/SANDUSDT 4h E2.0: n=548 exp=-0.00410 PF=0.539 PF2x=0.331 folds=3 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=2.231 verdict=FAIL
XRPUSDT/VETUSDT 4h E2.5: n=393 exp=-0.00592 PF=0.538 PF2x=0.389 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=2.159 verdict=FAIL
XRPUSDT/HBARUSDT 4h E2.5: n=393 exp=-0.00590 PF=0.538 PF2x=0.388 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=2.152 verdict=FAIL
XRPUSDT/DOGEUSDT 4h E2.5: n=393 exp=-0.00599 PF=0.538 PF2x=0.390 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=2.164 verdict=FAIL
ATOMUSDT/SANDUSDT 4h E2.5: n=548 exp=-0.00414 PF=0.536 PF2x=0.329 folds=3 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=2.256 verdict=FAIL
XRPUSDT/DOGEUSDT 4h E2.0: n=393 exp=-0.00605 PF=0.535 PF2x=0.388 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=2.164 verdict=FAIL
XRPUSDT/NEARUSDT 1h E2.0: n=1572 exp=-0.00384 PF=0.534 PF2x=0.327 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=5.694 verdict=FAIL
XRPUSDT/NEARUSDT 1h E2.5: n=1572 exp=-0.00384 PF=0.534 PF2x=0.327 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=5.694 verdict=FAIL
XRPUSDT/VETUSDT 4h E2.0: n=393 exp=-0.00603 PF=0.534 PF2x=0.386 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=2.159 verdict=FAIL
XRPUSDT/HBARUSDT 4h E2.0: n=393 exp=-0.00601 PF=0.533 PF2x=0.386 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=2.152 verdict=FAIL
BCHUSDT/MANAUSDT 4h E2.5: n=152 exp=-0.00386 PF=0.533 PF2x=0.317 folds=1 foldpos=0.00 p=9.95e-01 DSR=0.000 maxDD=0.516 verdict=FAIL
ATOMUSDT/BCHUSDT 4h E2.5: n=160 exp=-0.00356 PF=0.533 PF2x=0.302 folds=1 foldpos=0.00 p=9.96e-01 DSR=0.000 maxDD=0.475 verdict=FAIL
XRPUSDT/ALGOUSDT 4h E2.5: n=394 exp=-0.00586 PF=0.529 PF2x=0.379 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=2.169 verdict=FAIL
XRPUSDT/ARBUSDT 4h E2.5: n=394 exp=-0.00596 PF=0.528 PF2x=0.379 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=2.207 verdict=FAIL
BNBUSDT/SUIUSDT 4h E2.5: n=383 exp=-0.00338 PF=0.527 PF2x=0.303 folds=2 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=1.270 verdict=FAIL
XRPUSDT/ALGOUSDT 4h E2.0: n=394 exp=-0.00592 PF=0.527 PF2x=0.377 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=2.169 verdict=FAIL
XRPUSDT/ARBUSDT 4h E2.0: n=394 exp=-0.00601 PF=0.526 PF2x=0.378 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=2.207 verdict=FAIL
XRPUSDT/UNIUSDT 4h E2.5: n=393 exp=-0.00572 PF=0.517 PF2x=0.362 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=2.099 verdict=FAIL
XRPUSDT/AAVEUSDT 1h E2.5: n=1566 exp=-0.00309 PF=0.515 PF2x=0.270 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=4.822 verdict=FAIL
XRPUSDT/UNIUSDT 4h E2.0: n=393 exp=-0.00583 PF=0.512 PF2x=0.359 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=2.099 verdict=FAIL
XRPUSDT/OPUSDT 4h E2.5: n=394 exp=-0.00589 PF=0.511 PF2x=0.360 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=2.187 verdict=FAIL
XRPUSDT/AAVEUSDT 1h E2.0: n=1566 exp=-0.00315 PF=0.510 PF2x=0.268 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=4.822 verdict=FAIL
XRPUSDT/OPUSDT 4h E2.0: n=394 exp=-0.00593 PF=0.510 PF2x=0.359 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=2.187 verdict=FAIL
DOTUSDT/BCHUSDT 4h E2.5: n=164 exp=-0.00397 PF=0.508 PF2x=0.292 folds=1 foldpos=0.00 p=9.97e-01 DSR=0.000 maxDD=0.523 verdict=FAIL
XRPUSDT/TRXUSDT 4h E2.0: n=394 exp=-0.00680 PF=0.508 PF2x=0.372 folds=2 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=2.462 verdict=FAIL
ATOMUSDT/BCHUSDT 4h E2.0: n=160 exp=-0.00407 PF=0.500 PF2x=0.287 folds=1 foldpos=0.00 p=9.93e-01 DSR=0.000 maxDD=0.475 verdict=FAIL
XRPUSDT/APTUSDT 4h E2.5: n=392 exp=-0.00357 PF=0.494 PF2x=0.264 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=1.373 verdict=FAIL
ADAUSDT/XLMUSDT 4h E2.0: n=459 exp=-0.00291 PF=0.493 PF2x=0.248 folds=3 foldpos=0.33 p=1.00e+00 DSR=0.000 maxDD=1.293 verdict=FAIL
AVAXUSDT/BCHUSDT 4h E2.5: n=167 exp=-0.00415 PF=0.483 PF2x=0.274 folds=1 foldpos=0.00 p=9.98e-01 DSR=0.000 maxDD=0.565 verdict=FAIL
XRPUSDT/SUIUSDT 1h E2.5: n=1572 exp=-0.00367 PF=0.480 PF2x=0.266 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=5.585 verdict=FAIL
XRPUSDT/APTUSDT 4h E2.0: n=392 exp=-0.00378 PF=0.479 PF2x=0.258 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=1.373 verdict=FAIL
XRPUSDT/SUIUSDT 1h E2.0: n=1572 exp=-0.00369 PF=0.479 PF2x=0.265 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=5.585 verdict=FAIL
DOTUSDT/BCHUSDT 4h E2.0: n=164 exp=-0.00453 PF=0.475 PF2x=0.277 folds=1 foldpos=0.00 p=9.94e-01 DSR=0.000 maxDD=0.523 verdict=FAIL
LINKUSDT/AAVEUSDT 4h E2.5: n=237 exp=-0.00449 PF=0.473 PF2x=0.280 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=0.998 verdict=FAIL
XRPUSDT/DOGEUSDT 1h E2.5: n=1573 exp=-0.00364 PF=0.473 PF2x=0.258 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=5.550 verdict=FAIL
XRPUSDT/DOGEUSDT 1h E2.0: n=1573 exp=-0.00366 PF=0.472 PF2x=0.258 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=5.550 verdict=FAIL
XRPUSDT/VETUSDT 1h E2.5: n=1572 exp=-0.00362 PF=0.472 PF2x=0.256 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=5.528 verdict=FAIL
XRPUSDT/VETUSDT 1h E2.0: n=1572 exp=-0.00364 PF=0.471 PF2x=0.256 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=5.528 verdict=FAIL
XLMUSDT/ALGOUSDT 4h E2.5: n=389 exp=-0.00435 PF=0.469 PF2x=0.275 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=1.647 verdict=FAIL
XRPUSDT/HBARUSDT 1h E2.5: n=1571 exp=-0.00365 PF=0.468 PF2x=0.254 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=5.555 verdict=FAIL
ALGOUSDT/SANDUSDT 4h E2.5: n=373 exp=-0.00273 PF=0.468 PF2x=0.225 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=1.000 verdict=FAIL
XRPUSDT/HBARUSDT 1h E2.0: n=1571 exp=-0.00367 PF=0.467 PF2x=0.253 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=5.555 verdict=FAIL
LINKUSDT/AAVEUSDT 4h E2.0: n=237 exp=-0.00460 PF=0.467 PF2x=0.277 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=0.998 verdict=FAIL
XLMUSDT/ALGOUSDT 4h E2.0: n=389 exp=-0.00444 PF=0.464 PF2x=0.273 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=1.647 verdict=FAIL
OPUSDT/INJUSDT 1h E2.5: n=262 exp=-0.00420 PF=0.463 PF2x=0.262 folds=1 foldpos=0.00 p=9.97e-01 DSR=0.000 maxDD=1.092 verdict=FAIL
ALGOUSDT/SANDUSDT 4h E2.0: n=373 exp=-0.00281 PF=0.461 PF2x=0.223 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=1.000 verdict=FAIL
ADAUSDT/XLMUSDT 4h E2.5: n=459 exp=-0.00303 PF=0.460 PF2x=0.221 folds=3 foldpos=0.33 p=1.00e+00 DSR=0.000 maxDD=1.351 verdict=FAIL
XRPUSDT/SANDUSDT 1h E2.5: n=1576 exp=-0.00362 PF=0.459 PF2x=0.244 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=5.586 verdict=FAIL
XRPUSDT/SANDUSDT 1h E2.0: n=1576 exp=-0.00362 PF=0.459 PF2x=0.244 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=5.586 verdict=FAIL
XRPUSDT/MANAUSDT 1h E2.5: n=1576 exp=-0.00362 PF=0.457 PF2x=0.243 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=5.578 verdict=FAIL
XRPUSDT/MANAUSDT 1h E2.0: n=1576 exp=-0.00362 PF=0.457 PF2x=0.243 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=5.578 verdict=FAIL
AVAXUSDT/BCHUSDT 4h E2.0: n=167 exp=-0.00463 PF=0.456 PF2x=0.262 folds=1 foldpos=0.00 p=9.96e-01 DSR=0.000 maxDD=0.565 verdict=FAIL
APTUSDT/SANDUSDT 4h E2.0: n=169 exp=-0.00628 PF=0.455 PF2x=0.302 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=1.089 verdict=FAIL
HBARUSDT/ALGOUSDT 1h E2.0: n=65 exp=-0.00348 PF=0.454 PF2x=0.243 folds=1 foldpos=0.00 p=9.35e-01 DSR=0.000 maxDD=0.346 verdict=FAIL
DOTUSDT/ALGOUSDT 1h E2.0: n=1701 exp=-0.00315 PF=0.447 PF2x=0.212 folds=2 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=5.410 verdict=FAIL
AVAXUSDT/ALGOUSDT 1h E2.0: n=1412 exp=-0.00350 PF=0.444 PF2x=0.217 folds=2 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=5.000 verdict=FAIL
APTUSDT/SANDUSDT 1h E2.0: n=670 exp=-0.00366 PF=0.444 PF2x=0.219 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=2.505 verdict=FAIL
OPUSDT/INJUSDT 4h E2.0: n=67 exp=-0.01275 PF=0.442 PF2x=0.357 folds=2 foldpos=0.50 p=8.94e-01 DSR=0.000 maxDD=0.874 verdict=FAIL
XRPUSDT/UNIUSDT 1h E2.5: n=1570 exp=-0.00360 PF=0.441 PF2x=0.227 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=5.520 verdict=FAIL
DOTUSDT/ALGOUSDT 1h E2.5: n=1700 exp=-0.00320 PF=0.440 PF2x=0.208 folds=2 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=5.424 verdict=FAIL
ATOMUSDT/APTUSDT 4h E2.5: n=74 exp=-0.00360 PF=0.440 PF2x=0.233 folds=1 foldpos=0.00 p=9.90e-01 DSR=0.000 maxDD=0.308 verdict=FAIL
XRPUSDT/UNIUSDT 1h E2.0: n=1570 exp=-0.00364 PF=0.438 PF2x=0.226 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=5.520 verdict=FAIL
XRPUSDT/TRXUSDT 1h E2.5: n=1573 exp=-0.00392 PF=0.436 PF2x=0.230 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=5.980 verdict=FAIL
XRPUSDT/TRXUSDT 1h E2.0: n=1573 exp=-0.00393 PF=0.436 PF2x=0.230 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=5.980 verdict=FAIL
DOTUSDT/ETCUSDT 1h E2.0: n=224 exp=-0.00313 PF=0.434 PF2x=0.203 folds=1 foldpos=0.00 p=9.93e-01 DSR=0.000 maxDD=0.875 verdict=FAIL
APTUSDT/SANDUSDT 1h E2.5: n=670 exp=-0.00385 PF=0.431 PF2x=0.214 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=2.505 verdict=FAIL
AVAXUSDT/ALGOUSDT 1h E2.5: n=1412 exp=-0.00373 PF=0.428 PF2x=0.210 folds=2 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=5.001 verdict=FAIL
DOTUSDT/AVAXUSDT 4h E2.0: n=231 exp=-0.00354 PF=0.427 PF2x=0.197 folds=1 foldpos=0.00 p=9.98e-01 DSR=0.000 maxDD=0.905 verdict=FAIL
ATOMUSDT/APTUSDT 4h E2.0: n=74 exp=-0.00368 PF=0.427 PF2x=0.224 folds=1 foldpos=0.00 p=9.92e-01 DSR=0.000 maxDD=0.308 verdict=FAIL
XRPUSDT/ARBUSDT 1h E2.5: n=1574 exp=-0.00389 PF=0.426 PF2x=0.220 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=5.986 verdict=FAIL
XRPUSDT/ARBUSDT 1h E2.0: n=1574 exp=-0.00390 PF=0.425 PF2x=0.219 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=5.986 verdict=FAIL
ATOMUSDT/MANAUSDT 4h E2.5: n=293 exp=-0.00523 PF=0.423 PF2x=0.252 folds=2 foldpos=0.00 p=9.98e-01 DSR=0.000 maxDD=1.471 verdict=FAIL
XRPUSDT/ALGOUSDT 1h E2.5: n=1574 exp=-0.00388 PF=0.422 PF2x=0.216 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=5.973 verdict=FAIL
XRPUSDT/ALGOUSDT 1h E2.0: n=1574 exp=-0.00389 PF=0.421 PF2x=0.216 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=5.973 verdict=FAIL
APTUSDT/SANDUSDT 4h E2.5: n=169 exp=-0.00700 PF=0.420 PF2x=0.280 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=1.089 verdict=FAIL
XRPUSDT/OPUSDT 1h E2.5: n=1574 exp=-0.00385 PF=0.409 PF2x=0.204 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=5.937 verdict=FAIL
XRPUSDT/OPUSDT 1h E2.0: n=1574 exp=-0.00387 PF=0.407 PF2x=0.203 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=5.937 verdict=FAIL
FILUSDT/ALGOUSDT 1h E2.0: n=1533 exp=-0.00339 PF=0.400 PF2x=0.177 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=5.290 verdict=FAIL
LTCUSDT/ETCUSDT 1h E2.5: n=1304 exp=-0.00331 PF=0.398 PF2x=0.169 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=4.038 verdict=FAIL
LTCUSDT/ETCUSDT 1h E2.0: n=1304 exp=-0.00332 PF=0.397 PF2x=0.169 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=4.038 verdict=FAIL
XRPUSDT/ADAUSDT 1h E2.5: n=1568 exp=-0.00382 PF=0.395 PF2x=0.192 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=5.866 verdict=FAIL
FILUSDT/ALGOUSDT 1h E2.5: n=1533 exp=-0.00342 PF=0.395 PF2x=0.174 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=5.290 verdict=FAIL
BNBUSDT/AAVEUSDT 4h E2.5: n=337 exp=-0.00395 PF=0.394 PF2x=0.193 folds=2 foldpos=0.50 p=1.00e+00 DSR=0.000 maxDD=1.398 verdict=FAIL
DOTUSDT/AVAXUSDT 4h E2.5: n=230 exp=-0.00365 PF=0.394 PF2x=0.168 folds=1 foldpos=0.00 p=9.99e-01 DSR=0.000 maxDD=0.905 verdict=FAIL
XRPUSDT/ADAUSDT 1h E2.0: n=1568 exp=-0.00385 PF=0.394 PF2x=0.192 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=5.866 verdict=FAIL
XRPUSDT/ETCUSDT 4h E2.5: n=393 exp=-0.00489 PF=0.393 PF2x=0.219 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=1.837 verdict=FAIL
XRPUSDT/ETCUSDT 4h E2.0: n=393 exp=-0.00492 PF=0.391 PF2x=0.219 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=1.837 verdict=FAIL
OPUSDT/INJUSDT 1h E2.0: n=263 exp=-0.00572 PF=0.391 PF2x=0.230 folds=2 foldpos=0.50 p=9.89e-01 DSR=0.000 maxDD=1.541 verdict=FAIL
ATOMUSDT/MANAUSDT 4h E2.0: n=293 exp=-0.00611 PF=0.386 PF2x=0.234 folds=2 foldpos=0.00 p=9.98e-01 DSR=0.000 maxDD=1.540 verdict=FAIL
XLMUSDT/MANAUSDT 4h E2.0: n=400 exp=-0.00492 PF=0.386 PF2x=0.213 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=1.922 verdict=FAIL
XLMUSDT/MANAUSDT 4h E2.5: n=400 exp=-0.00492 PF=0.386 PF2x=0.213 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=1.922 verdict=FAIL
BNBUSDT/AAVEUSDT 4h E2.0: n=337 exp=-0.00404 PF=0.382 PF2x=0.186 folds=2 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=1.398 verdict=FAIL
XLMUSDT/SANDUSDT 4h E2.5: n=401 exp=-0.00536 PF=0.378 PF2x=0.216 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=2.092 verdict=FAIL
XLMUSDT/SANDUSDT 4h E2.0: n=401 exp=-0.00536 PF=0.378 PF2x=0.216 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=2.092 verdict=FAIL
SOLUSDT/ETCUSDT 4h E2.0: n=60 exp=-0.00559 PF=0.377 PF2x=0.215 folds=1 foldpos=0.00 p=9.77e-01 DSR=0.000 maxDD=0.376 verdict=FAIL
BCHUSDT/FILUSDT 4h E2.5: n=257 exp=-0.00517 PF=0.368 PF2x=0.202 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=1.283 verdict=FAIL
ATOMUSDT/SANDUSDT 1h E2.5: n=2169 exp=-0.00319 PF=0.367 PF2x=0.143 folds=2 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=6.934 verdict=FAIL
ETCUSDT/ALGOUSDT 4h E2.5: n=138 exp=-0.00520 PF=0.365 PF2x=0.196 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=0.612 verdict=FAIL
ATOMUSDT/SANDUSDT 1h E2.0: n=2169 exp=-0.00326 PF=0.362 PF2x=0.142 folds=2 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=6.934 verdict=FAIL
ETCUSDT/HBARUSDT 1h E2.0: n=162 exp=-0.00350 PF=0.361 PF2x=0.164 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=0.648 verdict=FAIL
ETCUSDT/BCHUSDT 4h E2.5: n=210 exp=-0.00524 PF=0.357 PF2x=0.193 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=0.983 verdict=FAIL
APTUSDT/MANAUSDT 1h E2.5: n=497 exp=-0.00427 PF=0.356 PF2x=0.165 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=1.883 verdict=FAIL
APTUSDT/MANAUSDT 1h E2.0: n=497 exp=-0.00428 PF=0.355 PF2x=0.165 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=1.883 verdict=FAIL
ETCUSDT/BCHUSDT 4h E2.0: n=210 exp=-0.00530 PF=0.354 PF2x=0.192 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=0.983 verdict=FAIL
ADAUSDT/XLMUSDT 1h E2.0: n=286 exp=-0.00303 PF=0.351 PF2x=0.165 folds=2 foldpos=0.50 p=9.98e-01 DSR=0.000 maxDD=1.164 verdict=FAIL
APTUSDT/MANAUSDT 4h E2.5: n=125 exp=-0.00829 PF=0.351 PF2x=0.232 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=0.848 verdict=FAIL
ETCUSDT/HBARUSDT 1h E2.5: n=162 exp=-0.00358 PF=0.347 PF2x=0.155 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=0.648 verdict=FAIL
BCHUSDT/FILUSDT 4h E2.0: n=257 exp=-0.00568 PF=0.346 PF2x=0.193 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=1.283 verdict=FAIL
DOTUSDT/APTUSDT 1h E2.5: n=505 exp=-0.00327 PF=0.342 PF2x=0.146 folds=2 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=1.961 verdict=FAIL
BNBUSDT/TRXUSDT 1h E2.5: n=1062 exp=-0.00308 PF=0.336 PF2x=0.136 folds=2 foldpos=0.50 p=1.00e+00 DSR=0.000 maxDD=3.634 verdict=FAIL
APTUSDT/MANAUSDT 4h E2.0: n=125 exp=-0.00890 PF=0.335 PF2x=0.223 folds=1 foldpos=0.00 p=9.99e-01 DSR=0.000 maxDD=0.848 verdict=FAIL
XRPUSDT/FILUSDT 1h E2.5: n=1574 exp=-0.00370 PF=0.329 PF2x=0.139 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=5.709 verdict=FAIL
XRPUSDT/FILUSDT 1h E2.0: n=1574 exp=-0.00372 PF=0.328 PF2x=0.138 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=5.709 verdict=FAIL
ETCUSDT/ALGOUSDT 4h E2.0: n=138 exp=-0.00622 PF=0.325 PF2x=0.179 folds=1 foldpos=0.00 p=9.98e-01 DSR=0.000 maxDD=0.612 verdict=FAIL
FILUSDT/APTUSDT 4h E2.5: n=120 exp=-0.00578 PF=0.323 PF2x=0.173 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=0.634 verdict=FAIL
XRPUSDT/ATOMUSDT 1h E2.0: n=1575 exp=-0.00368 PF=0.319 PF2x=0.131 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=5.682 verdict=FAIL
XRPUSDT/ATOMUSDT 1h E2.5: n=1575 exp=-0.00368 PF=0.319 PF2x=0.131 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=5.682 verdict=FAIL
DOTUSDT/APTUSDT 1h E2.0: n=505 exp=-0.00341 PF=0.319 PF2x=0.132 folds=2 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=1.980 verdict=FAIL
DOTUSDT/ETCUSDT 1h E2.5: n=223 exp=-0.00353 PF=0.317 PF2x=0.113 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=0.691 verdict=FAIL
SOLUSDT/ETCUSDT 4h E2.5: n=60 exp=-0.00669 PF=0.317 PF2x=0.181 folds=1 foldpos=0.00 p=9.90e-01 DSR=0.000 maxDD=0.376 verdict=FAIL
XRPUSDT/DOTUSDT 1h E2.5: n=1574 exp=-0.00366 PF=0.316 PF2x=0.129 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=5.637 verdict=FAIL
XRPUSDT/DOTUSDT 1h E2.0: n=1574 exp=-0.00368 PF=0.315 PF2x=0.129 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=5.637 verdict=FAIL
BNBUSDT/TRXUSDT 1h E2.0: n=1062 exp=-0.00323 PF=0.312 PF2x=0.121 folds=2 foldpos=0.50 p=1.00e+00 DSR=0.000 maxDD=3.687 verdict=FAIL
FILUSDT/APTUSDT 4h E2.0: n=120 exp=-0.00611 PF=0.311 PF2x=0.168 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=0.634 verdict=FAIL
BNBUSDT/XLMUSDT 1h E2.5: n=1310 exp=-0.00313 PF=0.308 PF2x=0.119 folds=2 foldpos=0.50 p=1.00e+00 DSR=0.000 maxDD=4.407 verdict=FAIL
ETCUSDT/FILUSDT 1h E2.5: n=225 exp=-0.00392 PF=0.298 PF2x=0.111 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=0.747 verdict=FAIL
BNBUSDT/SUIUSDT 1h E2.0: n=1521 exp=-0.00323 PF=0.292 PF2x=0.112 folds=2 foldpos=0.50 p=1.00e+00 DSR=0.000 maxDD=5.183 verdict=FAIL
BNBUSDT/XLMUSDT 1h E2.0: n=1310 exp=-0.00325 PF=0.288 PF2x=0.107 folds=2 foldpos=0.50 p=1.00e+00 DSR=0.000 maxDD=4.458 verdict=FAIL
ETCUSDT/FILUSDT 1h E2.0: n=225 exp=-0.00417 PF=0.285 PF2x=0.107 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=0.747 verdict=FAIL
XRPUSDT/INJUSDT 4h E2.0: n=393 exp=-0.00520 PF=0.277 PF2x=0.130 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=1.985 verdict=FAIL
XRPUSDT/INJUSDT 4h E2.5: n=393 exp=-0.00522 PF=0.276 PF2x=0.130 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=1.985 verdict=FAIL
BCHUSDT/FILUSDT 1h E2.5: n=1015 exp=-0.00349 PF=0.276 PF2x=0.091 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=3.473 verdict=FAIL
XRPUSDT/ETCUSDT 1h E2.5: n=1570 exp=-0.00351 PF=0.276 PF2x=0.100 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=5.430 verdict=FAIL
XRPUSDT/ETCUSDT 1h E2.0: n=1570 exp=-0.00354 PF=0.273 PF2x=0.099 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=5.430 verdict=FAIL
BCHUSDT/MANAUSDT 1h E2.0: n=612 exp=-0.00346 PF=0.269 PF2x=0.081 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=2.135 verdict=FAIL
BCHUSDT/FILUSDT 1h E2.0: n=1015 exp=-0.00362 PF=0.268 PF2x=0.089 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=3.473 verdict=FAIL
ATOMUSDT/MANAUSDT 1h E2.5: n=1165 exp=-0.00370 PF=0.268 PF2x=0.091 folds=2 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=4.281 verdict=FAIL
ATOMUSDT/BCHUSDT 1h E2.5: n=638 exp=-0.00346 PF=0.264 PF2x=0.075 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=2.126 verdict=FAIL
ATOMUSDT/BCHUSDT 1h E2.0: n=638 exp=-0.00359 PF=0.257 PF2x=0.074 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=2.126 verdict=FAIL
BCHUSDT/MANAUSDT 1h E2.5: n=611 exp=-0.00362 PF=0.257 PF2x=0.076 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=2.135 verdict=FAIL
ATOMUSDT/MANAUSDT 1h E2.0: n=1165 exp=-0.00393 PF=0.256 PF2x=0.088 folds=2 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=4.353 verdict=FAIL
XRPUSDT/APTUSDT 1h E2.5: n=1567 exp=-0.00363 PF=0.255 PF2x=0.093 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=5.600 verdict=FAIL
XRPUSDT/APTUSDT 1h E2.0: n=1567 exp=-0.00363 PF=0.255 PF2x=0.093 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=5.600 verdict=FAIL
BNBUSDT/SUIUSDT 1h E2.5: n=1520 exp=-0.00338 PF=0.254 PF2x=0.088 folds=2 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=5.123 verdict=FAIL
XLMUSDT/MANAUSDT 1h E2.5: n=1600 exp=-0.00359 PF=0.252 PF2x=0.086 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=5.738 verdict=FAIL
BNBUSDT/BCHUSDT 1h E2.5: n=769 exp=-0.00314 PF=0.252 PF2x=0.085 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=2.391 verdict=FAIL
XLMUSDT/MANAUSDT 1h E2.0: n=1600 exp=-0.00360 PF=0.252 PF2x=0.086 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=5.738 verdict=FAIL
BNBUSDT/BCHUSDT 1h E2.0: n=769 exp=-0.00316 PF=0.251 PF2x=0.085 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=2.391 verdict=FAIL
ETCUSDT/ALGOUSDT 1h E2.5: n=540 exp=-0.00329 PF=0.250 PF2x=0.078 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=1.689 verdict=FAIL
BNBUSDT/SANDUSDT 1h E2.5: n=187 exp=-0.00382 PF=0.247 PF2x=0.092 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=0.582 verdict=FAIL
XRPUSDT/AVAXUSDT 4h E2.0: n=393 exp=-0.00472 PF=0.245 PF2x=0.088 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=1.816 verdict=FAIL
XRPUSDT/AVAXUSDT 4h E2.5: n=393 exp=-0.00474 PF=0.244 PF2x=0.088 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=1.816 verdict=FAIL
BNBUSDT/SANDUSDT 1h E2.0: n=187 exp=-0.00396 PF=0.240 PF2x=0.090 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=0.582 verdict=FAIL
FILUSDT/APTUSDT 1h E2.5: n=476 exp=-0.00394 PF=0.237 PF2x=0.074 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=1.787 verdict=FAIL
BCHUSDT/ARBUSDT 1h E2.0: n=669 exp=-0.00391 PF=0.236 PF2x=0.076 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=2.442 verdict=FAIL
BCHUSDT/ARBUSDT 1h E2.5: n=669 exp=-0.00391 PF=0.236 PF2x=0.076 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=2.442 verdict=FAIL
ETCUSDT/ALGOUSDT 1h E2.0: n=540 exp=-0.00357 PF=0.236 PF2x=0.075 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=1.689 verdict=FAIL
DOTUSDT/BCHUSDT 1h E2.5: n=655 exp=-0.00385 PF=0.235 PF2x=0.075 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=2.337 verdict=FAIL
FILUSDT/APTUSDT 1h E2.0: n=476 exp=-0.00400 PF=0.234 PF2x=0.073 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=1.787 verdict=FAIL
DOTUSDT/BCHUSDT 1h E2.0: n=655 exp=-0.00389 PF=0.233 PF2x=0.075 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=2.337 verdict=FAIL
BNBUSDT/VETUSDT 4h E2.5: n=51 exp=-0.00599 PF=0.232 PF2x=0.108 folds=1 foldpos=0.00 p=9.92e-01 DSR=0.000 maxDD=0.205 verdict=FAIL
AVAXUSDT/BCHUSDT 1h E2.5: n=665 exp=-0.00375 PF=0.231 PF2x=0.071 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=2.356 verdict=FAIL
ETCUSDT/BCHUSDT 1h E2.5: n=830 exp=-0.00373 PF=0.230 PF2x=0.074 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=2.983 verdict=FAIL
ETCUSDT/BCHUSDT 1h E2.0: n=830 exp=-0.00374 PF=0.230 PF2x=0.074 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=2.983 verdict=FAIL
ALGOUSDT/MANAUSDT 4h E2.5: n=357 exp=-0.00436 PF=0.230 PF2x=0.089 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=1.565 verdict=FAIL
ALGOUSDT/MANAUSDT 4h E2.0: n=357 exp=-0.00439 PF=0.226 PF2x=0.087 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=1.565 verdict=FAIL
BNBUSDT/AAVEUSDT 1h E2.5: n=1334 exp=-0.00336 PF=0.225 PF2x=0.071 folds=2 foldpos=0.50 p=1.00e+00 DSR=0.000 maxDD=4.513 verdict=FAIL
AVAXUSDT/BCHUSDT 1h E2.0: n=665 exp=-0.00387 PF=0.225 PF2x=0.070 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=2.356 verdict=FAIL
XRPUSDT/INJUSDT 1h E2.5: n=1572 exp=-0.00344 PF=0.221 PF2x=0.068 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=5.342 verdict=FAIL
BNBUSDT/AAVEUSDT 1h E2.0: n=1334 exp=-0.00339 PF=0.221 PF2x=0.069 folds=2 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=4.513 verdict=FAIL
ETCUSDT/HBARUSDT 4h E2.0: n=46 exp=-0.01074 PF=0.221 PF2x=0.131 folds=2 foldpos=0.00 p=9.67e-01 DSR=0.000 maxDD=0.312 verdict=FAIL
XRPUSDT/INJUSDT 1h E2.0: n=1572 exp=-0.00348 PF=0.219 PF2x=0.067 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=5.342 verdict=FAIL
BNBUSDT/VETUSDT 4h E2.0: n=51 exp=-0.00662 PF=0.215 PF2x=0.101 folds=1 foldpos=0.00 p=9.85e-01 DSR=0.000 maxDD=0.205 verdict=FAIL
ALGOUSDT/SANDUSDT 1h E2.5: n=1492 exp=-0.00313 PF=0.202 PF2x=0.074 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=4.629 verdict=FAIL
ALGOUSDT/SANDUSDT 1h E2.0: n=1492 exp=-0.00315 PF=0.201 PF2x=0.074 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=4.638 verdict=FAIL
BNBUSDT/DOGEUSDT 1h E2.5: n=138 exp=-0.00379 PF=0.198 PF2x=0.058 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=0.387 verdict=FAIL
ATOMUSDT/APTUSDT 1h E2.5: n=286 exp=-0.00352 PF=0.195 PF2x=0.067 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=1.062 verdict=FAIL
BNBUSDT/LINKUSDT 1h E2.0: n=109 exp=-0.00471 PF=0.193 PF2x=0.066 folds=1 foldpos=0.00 p=9.97e-01 DSR=0.000 maxDD=0.343 verdict=FAIL
ATOMUSDT/APTUSDT 1h E2.0: n=286 exp=-0.00355 PF=0.189 PF2x=0.063 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=1.062 verdict=FAIL
BNBUSDT/VETUSDT 1h E2.0: n=202 exp=-0.00382 PF=0.187 PF2x=0.045 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=0.661 verdict=FAIL
BNBUSDT/VETUSDT 1h E2.5: n=202 exp=-0.00383 PF=0.187 PF2x=0.045 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=0.661 verdict=FAIL
BNBUSDT/ALGOUSDT 1h E2.5: n=55 exp=-0.00532 PF=0.185 PF2x=0.040 folds=1 foldpos=0.00 p=9.98e-01 DSR=0.000 maxDD=0.234 verdict=FAIL
BNBUSDT/LINKUSDT 1h E2.5: n=109 exp=-0.00495 PF=0.185 PF2x=0.064 folds=1 foldpos=0.00 p=9.95e-01 DSR=0.000 maxDD=0.343 verdict=FAIL
XRPUSDT/AVAXUSDT 1h E2.5: n=1571 exp=-0.00331 PF=0.184 PF2x=0.049 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=5.118 verdict=FAIL
ETCUSDT/HBARUSDT 4h E2.5: n=46 exp=-0.00846 PF=0.183 PF2x=0.081 folds=2 foldpos=0.00 p=9.99e-01 DSR=0.000 maxDD=0.331 verdict=FAIL
XRPUSDT/AVAXUSDT 1h E2.0: n=1571 exp=-0.00335 PF=0.182 PF2x=0.049 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=5.118 verdict=FAIL
XRPUSDT/LINKUSDT 1h E2.5: n=1572 exp=-0.00336 PF=0.182 PF2x=0.047 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=5.193 verdict=FAIL
XRPUSDT/LINKUSDT 1h E2.0: n=1572 exp=-0.00340 PF=0.180 PF2x=0.047 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=5.193 verdict=FAIL
BNBUSDT/DOGEUSDT 1h E2.0: n=138 exp=-0.00443 PF=0.175 PF2x=0.054 folds=1 foldpos=0.00 p=9.96e-01 DSR=0.000 maxDD=0.387 verdict=FAIL
BNBUSDT/SANDUSDT 4h E2.5: n=47 exp=-0.00693 PF=0.175 PF2x=0.076 folds=1 foldpos=0.00 p=9.90e-01 DSR=0.000 maxDD=0.201 verdict=FAIL
BNBUSDT/SANDUSDT 4h E2.0: n=47 exp=-0.00763 PF=0.161 PF2x=0.072 folds=1 foldpos=0.00 p=9.83e-01 DSR=0.000 maxDD=0.201 verdict=FAIL
ALGOUSDT/MANAUSDT 1h E2.5: n=1424 exp=-0.00323 PF=0.153 PF2x=0.037 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=4.616 verdict=FAIL
ALGOUSDT/MANAUSDT 1h E2.0: n=1424 exp=-0.00324 PF=0.151 PF2x=0.037 folds=1 foldpos=0.00 p=1.00e+00 DSR=0.000 maxDD=4.616 verdict=FAIL
BNBUSDT/ALGOUSDT 1h E2.0: n=55 exp=-0.00708 PF=0.146 PF2x=0.033 folds=1 foldpos=0.00 p=9.81e-01 DSR=0.000 maxDD=0.234 verdict=FAIL
ADAUSDT/XLMUSDT 1h E2.5: n=285 exp=-0.00386 PF=0.144 PF2x=0.035 folds=2 foldpos=0.50 p=1.00e+00 DSR=0.000 maxDD=1.113 verdict=FAIL
BNBUSDT/DOGEUSDT 4h E2.5: n=35 exp=-0.00793 PF=0.131 PF2x=0.041 folds=1 foldpos=0.00 p=9.74e-01 DSR=0.000 maxDD=0.147 verdict=FAIL
BNBUSDT/MANAUSDT 4h E2.5: n=36 exp=-0.00844 PF=0.128 PF2x=0.043 folds=1 foldpos=0.00 p=9.65e-01 DSR=0.000 maxDD=0.146 verdict=FAIL
BNBUSDT/UNIUSDT 1h E2.5: n=100 exp=-0.00619 PF=0.121 PF2x=0.030 folds=1 foldpos=0.00 p=9.99e-01 DSR=0.000 maxDD=0.532 verdict=FAIL
BNBUSDT/UNIUSDT 1h E2.0: n=100 exp=-0.00623 PF=0.120 PF2x=0.030 folds=1 foldpos=0.00 p=9.99e-01 DSR=0.000 maxDD=0.532 verdict=FAIL
BNBUSDT/MANAUSDT 4h E2.0: n=36 exp=-0.00936 PF=0.116 PF2x=0.040 folds=1 foldpos=0.00 p=9.54e-01 DSR=0.000 maxDD=0.146 verdict=FAIL
BNBUSDT/DOGEUSDT 4h E2.0: n=35 exp=-0.01034 PF=0.104 PF2x=0.034 folds=1 foldpos=0.00 p=9.47e-01 DSR=0.000 maxDD=0.147 verdict=FAIL
DOTUSDT/SANDUSDT 1h E2.5: n=36 exp=-0.01427 PF=0.101 PF2x=0.056 folds=2 foldpos=0.00 p=9.72e-01 DSR=0.000 maxDD=0.359 verdict=FAIL
ADAUSDT/ARBUSDT 1h E2.5: n=42 exp=-0.00808 PF=0.036 PF2x=0.012 folds=1 foldpos=0.00 p=9.82e-01 DSR=0.000 maxDD=0.186 verdict=FAIL
ADAUSDT/ARBUSDT 1h E2.0: n=42 exp=-0.00812 PF=0.035 PF2x=0.012 folds=1 foldpos=0.00 p=9.82e-01 DSR=0.000 maxDD=0.186 verdict=FAIL

## BTC/ETH headline pair rows

## Cost drag: PF on gross (zero-cost) vs net, configs n>=200
configs with gross PF>=1.2: 5 of 186
configs with net PF>=1.2: 0 of 186
basis                     gross    net
pair              tf E                
LINKUSDT/ALGOUSDT 1h 2.5  1.565  0.680
                     2.0  1.555  0.686
NEARUSDT/OPUSDT   1h 2.0  1.429  0.766
                     2.5  1.364  0.721
BNBUSDT/TRXUSDT   4h 2.5  1.265  0.760
BNBUSDT/XLMUSDT   4h 2.5  1.199  0.681
                     2.0  1.149  0.655
BNBUSDT/TRXUSDT   4h 2.0  1.148  0.687
ALGOUSDT/SANDUSDT 4h 2.5  1.148  0.468
XRPUSDT/AAVEUSDT  4h 2.5  1.125  0.797
ALGOUSDT/SANDUSDT 4h 2.0  1.119  0.461
XRPUSDT/AAVEUSDT  4h 2.0  1.112  0.789

## Exit reasons / holding (all fold trades)
reason
stop          164078
window_end       333
mean_cross       159
bars held: mean=2.8 median=1 max=2903
total fold trades: 164570; total net (sum over all configs, overlapping): -597.935

## Procedure level (from synthesis)
1h|E2.0: n=65774 exp=-0.00349 PF=0.384 PF2x=0.179 p=1.00e+00 DSR=0.000 total=-229.443 folds={'W1': -16.479, 'W2': -164.008, 'W3': -22.876, 'W4': -22.944, 'W5': -3.136}
1h|E2.5: n=65748 exp=-0.00348 PF=0.381 PF2x=0.176 p=1.00e+00 DSR=0.000 total=-228.497 folds={'W1': -16.594, 'W2': -163.275, 'W3': -21.817, 'W4': -23.956, 'W5': -2.855}
4h|E2.0: n=16540 exp=-0.00426 PF=0.574 PF2x=0.387 p=1.00e+00 DSR=0.000 total=-70.402 folds={'W1': -6.555, 'W2': -54.415, 'W3': -3.605, 'W4': -5.428, 'W5': -0.4}
4h|E2.5: n=16508 exp=-0.00422 PF=0.566 PF2x=0.376 p=1.00e+00 DSR=0.000 total=-69.593 folds={'W1': -7.304, 'W2': -52.981, 'W3': -3.805, 'W4': -5.188, 'W5': -0.315}
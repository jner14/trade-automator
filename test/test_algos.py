from unittest import TestCase
from algos import highs_lows


class TestHighs_lows(TestCase):
    def test_highs_lows(self):
        import sys
        import pandas as pd
        from datetime import datetime
        TIME = 'Intraday_Time'
        DATE = 'Intraday_Date'
        filename = 'SGC-LON.csv'

        # Read 5 minute bars from a csv file
        try:
            bars = pd.read_csv(filename)
        except Exception as e:
            print('{} >> Failed to load filename={}. '.format(e, filename))
            sys.exit()

        # Use time and date as an index
        try:
            bars.index = bars.apply(
                lambda row: datetime.strptime(row[TIME] + '-' + row[DATE], '%H:%M-%m/%d/%Y'), axis=1)
            # for k, v in bars.iterrows():
            #     datetime.strptime(v[TIME] + '-' + v[DATE], '%H:%M-%m/%d/%Y')
        except Exception as e:
            print("%s >> Failed to interpret date and time columns.  Ensure the following formats: 8:00, 1/1/2017" % e)

        # Extract previous day close from first row of data
        prevClose = bars.head(1)
        bars.drop(bars.index[0], inplace=True, axis=0)

        result = highs_lows(bars=bars,
                            prev_close=prevClose,
                            ma_period=2,
                            average_type=1,
                            pct_change=0.2,
                            full_df=True,
                            for_viewing=True)

        result.to_csv("%s High Low Output.csv" % filename[:-4], index=False)

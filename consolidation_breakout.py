import pandas as pd
from datetime import datetime, timedelta
import argparse
import sys

# Column headers
OPEN = 'Open'
HIGH = 'High'
LOW = 'Low'
LAST = 'Last'
TIME = 'Intraday_Time'
DATE = 'Intraday_Date'
COLUMN_LABELS = [OPEN, HIGH, LOW, LAST, TIME, DATE]


def consol_breakout(bars, min_adj_vol=100000, min_ma5std=2.0, min_ave_prc_chg=.003):
    """
    Detects if any breakout occurred during the given span of bars.
    Returns a DataFrame with a boolean field labeled Breakout and an index identical to the passed bars.
    """

    # Make sure there are at least 5 bars
    assert len(bars) >= 5, "[ERROR] make sure to pass at least 5 bars to consol_breakout()!"

    # Make sure data has required labels
    check_labels(bars.columns)

    # Calculate average price of open and last
    bars['AvePrice'] = bars[[OPEN, LAST]].mean(axis=1)

    # Calculate the candle height, (last - open) / average price
    bars['CandleHeight'] = (bars[LAST] - bars[OPEN]) / bars.AvePrice

    # Calculate the average price change
    bars['AvePriceChg'] = 0
    bars.ix[1:, 'AvePriceChg'] = [bars.ix[i, 'AvePrice'] / bars.ix[i - 1, 'AvePrice'] - 1 for i in range(1, len(bars))]

    # Calculate the adjusted volume by using previous volume for values over MIN_ADJ_VOLUME
    bars['AdjVol'] = bars.loc[bars.Volume <= min_adj_vol, 'Volume']
    bars.AdjVol.ffill(inplace=True)

    # Exclude the first so many bars of the day for AdjustedVolume
    msk = bars.index < bars.index[0] + timedelta(minutes=15)
    bars.loc[msk, 'AdjVol'] = 0

    # Calculate the cumulative adjusted volume
    bars['CumVol'] = bars.AdjVol.cumsum()

    # Calculate the average adjusted volume, i.e. average of volume up to the bar in question
    bars['AvgVolPerBar'] = 0
    bars.loc[~msk, 'AvgVolPerBar'] = [bars.loc[~msk].ix[:i + 1, 'AdjVol'].mean() for i in range(len(bars.loc[~msk]))]

    # Calculate the 5 bar moving average
    bars['MA5'] = bars.AvePrice.rolling(5).mean()
    bars.MA5.fillna(0, inplace=True)

    # Calculate the 5 bar moving average standard deviation
    bars['MA5STD'] = 0
    bars.ix[4:, 'MA5STD'] = [
        1000 * pd.concat([bars.ix[i - 4:i + 1, OPEN], bars.ix[i - 4:i + 1, LAST]]).std() / bars.ix[i, 'MA5']
        for i in range(4, len(bars))]

    # Iterate through each row of 5 minute bars and check for breakout conditions
    bars['Breakout'] = bars.apply(lambda v:
                                  True if v.MA5STD >= min_ma5std and v.AvePriceChg > min_ave_prc_chg else False, axis=1)
    bars['Breakout-1'] = bars['Breakout'].shift()
    bars['Breakout'] = bars.apply(lambda v: True if v.Breakout and not v['Breakout-1'] else False, axis=1)

    return bars[['Breakout']]


def check_labels(columns):
    # Make sure required columns exist and are labeled correctly
    for label in COLUMN_LABELS:
        assert label in columns, 'Can not find column header=%s. Required column headers: %s' % (
            label, COLUMN_LABELS)

if __name__ == '__main__':

    # Arg parsing allows passing parameters via the command line
    parser = argparse.ArgumentParser()
    parser.add_argument('-f', '--file', dest='filename', help="the filename of the input csv file, e.g. data.csv",
                        required=True)
    parser.add_argument('-v', '--vol', dest='volume', help="the block trade volume requirement, e.g. 100000",
                        type=int, default=100000)
    parser.add_argument('-s', '--std', dest='ma5std', help="the minimum breakout value for MA5STD, e.g. 2.0",
                        type=float, default=2.0)
    parser.add_argument('-c', '--chg', dest='pricechg', help="the minimum breakout value for price change, e.g. .003",
                        type=float, default=.003)
    p_args = parser.parse_args()

    # Read 5 minute bars from a csv file
    try:
        bars5 = pd.read_csv(p_args.filename)
    except Exception as e:
        print('{} >> Failed to load filename={}. '.format(e, p_args.filename))
        sys.exit()

    # Make sure data has required labels
    check_labels(bars5.columns)

    # Use time and date as an index
    try:
        bars5.index = bars5.apply(
            lambda row: datetime.strptime(row[TIME] + '-' + row[DATE], '%H:%M-%m/%d/%Y'), axis=1)
    except Exception as e:
        print("%s >> Failed to interpret date and time columns.  Ensure the following formats: 8:00, 1/1/2017" % e)

    # Extract previous day close from first row of data
    prevClose = bars5.head(1)
    bars5.drop(bars5.index[0], inplace=True, axis=0)

    result = consol_breakout(bars=bars5,
                             min_adj_vol=p_args.volume,
                             min_ma5std=p_args.ma5std,
                             min_ave_prc_chg=p_args.pricechg)
else:
    # Inform when imported
    print('[OK] consolidation_breakout imported')

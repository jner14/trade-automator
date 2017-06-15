import pandas as pd
from datetime import datetime, timedelta
import argparse
import sys

# General parameters
MIN_ADJUSTED_VOLUME = 100000
MA5STD_MIN = 2
MIN_AVE_PRICE_CHG = .003

# Column headers
OPEN = 'Open'
HIGH = 'High'
LOW = 'Low'
LAST = 'Last'
TIME = 'Intraday_Time'
DATE = 'Intraday_Date'
COLUMN_LABELS = [OPEN, HIGH, LOW, LAST, TIME, DATE]


if __name__ == '__main__':

    # Arg parsing allows passing parameters via the command line
    parser = argparse.ArgumentParser()
    parser.add_argument('-f', '--file', dest='filename', help="the filename of the input csv file, e.g. data.csv",
                        required=True)
    parser.add_argument('-v', '--vol', dest='volume', help="the block trade volume requirement, e.g. 100000",
                        type=int)
    parser.add_argument('-s', '--std', dest='ma5std', help="the minimum breakout value for MA5STD, e.g. 2.0",
                        type=float)
    parser.add_argument('-c', '--chg', dest='pricechg', help="the minimum breakout value for price change, e.g. .003",
                        type=float)
    p_args = parser.parse_args()

    # Set parameters from input
    if p_args.volume is not None:
        MIN_ADJUSTED_VOLUME = p_args.volume
    if p_args.ma5std is not None:
        MA5STD_MIN = p_args.ma5std
    if p_args.pricechg is not None:
        MIN_AVE_PRICE_CHG = p_args.pricechg

    # Read 5 minute bars from a csv file
    try:
        data = pd.read_csv(p_args.filename)
    except Exception as e:
        print('{} >> Failed to load filename={}. '.format(e, p_args.filename))
        sys.exit()

    # Make sure required columns exist and are labeled correctly
    for label in COLUMN_LABELS:
        assert label in data.columns, 'Can not find column header=%s. Required column headers: %s' % (
            label, COLUMN_LABELS)

    # Use time and date as an index
    try:
        data.index = data.apply(
            lambda row: datetime.strptime(row[TIME] + '-' + row[DATE], '%H:%M-%m/%d/%Y'), axis=1)
    except Exception as e:
        print("%s >> Failed to interpret date and time columns.  Ensure the following formats: 8:00, 1/1/2017" % e)

    # Extract previous day close from first row of data
    prevClose = data.head(1)
    data.drop(data.index[0], inplace=True, axis=0)

    # Calculate average price of open and last
    data['AvePrice'] = data[[OPEN, LAST]].mean(axis=1)

    # Calculate the candle height, (last - open) / average price
    data['CandleHeight'] = (data[LAST] - data[OPEN]) / data.AvePrice

    # Calculate the average price change
    data['AvePriceChg'] = 0
    data.ix[1:, 'AvePriceChg'] = [data.ix[i, 'AvePrice'] / data.ix[i - 1, 'AvePrice'] - 1 for i in range(1, len(data))]

    # Calculate the adjusted volume by using previous volume for values over MIN_ADJ_VOLUME
    data['AdjVol'] = data.loc[data.Volume <= MIN_ADJUSTED_VOLUME, 'Volume']
    data.AdjVol.ffill(inplace=True)

    # Exclude the first so many bars of the day for AdjustedVolume
    msk = data.index < data.index[0] + timedelta(minutes=15)
    data.loc[msk, 'AdjVol'] = 0

    # Calculate the cumulative adjusted volume
    data['CumVol'] = data.AdjVol.cumsum()

    # Calculate the average adjusted volume, i.e. average of volume up to the bar in question
    data['AvgVolPerBar'] = 0
    data.loc[~msk, 'AvgVolPerBar'] = [data.loc[~msk].ix[:i + 1, 'AdjVol'].mean() for i in range(len(data.loc[~msk]))]

    # Calculate the 5 bar moving average
    data['MA5'] = data.AvePrice.rolling(5).mean()
    data.MA5.fillna(0, inplace=True)

    # Calculate the 5 bar moving average standard deviation
    data['MA5STD'] = 0
    data.ix[4:, 'MA5STD'] = [
        1000 * pd.concat([data.ix[i - 4:i + 1, OPEN], data.ix[i - 4:i + 1, LAST]]).std() / data.ix[i, 'MA5']
        for i in range(4, len(data))]

    # Iterate through each row of 5 minute bars and check for breakout conditions
    BreakoutAlerted = False
    for k, v in data.iterrows():
        if v.MA5STD >= MA5STD_MIN and v.AvePriceChg > MIN_AVE_PRICE_CHG:
            if not BreakoutAlerted:
                print('Breakout at {:%H:%M}, MA5STD={}'.format(k.time(), round(v.MA5STD, 2)))
                BreakoutAlerted = True
        else:
            BreakoutAlerted = False

    print('Finished')

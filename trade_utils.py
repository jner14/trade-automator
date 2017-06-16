from datetime import time


def change_time(t, minutes):
    tot_min = t.hour * 60 + t.minute + minutes
    hour = tot_min / 60
    minute = tot_min - hour * 60
    return time(hour, minute)


if __name__ == '__main__':
    a_time = time(8)
    print(change_time(a_time, -1))

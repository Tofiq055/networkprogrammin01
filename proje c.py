import ntplib
from time import ctime, time
def print_time():
    ntp_client = ntplib.NTPClient()
    response = ntp_client.request('pool.ntp.org')
    print("The current time information received from the server: ", ctime(response.tx_time))
    print("Local time in your pc :", ctime(time()))
    
if __name__ == '__main__':
    print_time()



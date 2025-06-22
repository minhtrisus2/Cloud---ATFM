import pandas as pd
import random
from datetime import datetime

def generate_holistic_flight_schedule():
    """
    Tạo lịch bay giả lập để tổng nhu cầu (đến + đi) vượt 52 chuyến/giờ vào giờ cao điểm.
    """
    airlines = {
        'HVN': 'A321', 'VJC': 'A321', 'BBA': 'A320', 'VAG': 'B737',
        'SIA': 'B789', 'QTR': 'A359', 'CPA': 'A330', 'KAL': 'B777'
    }
    domestic_airports = ['VVNB', 'VVDN', 'VVCR', 'VVPQ', 'VVDL', 'VVBM', 'VVTH', 'VVCI']
    international_airports = ['VTBS', 'WSSS', 'VHHH', 'RKSI', 'WMKK', 'RPLL']
    all_airports = domestic_airports + international_airports
    
    total_capacity_per_hour = 52
    flight_data = []
    flight_id_counter = 1

    for hour in range(24):
        if 7 <= hour <= 10 or 14 <= hour <= 18 or 21 <= hour <= 23: # Giờ cao điểm
            # Tạo tổng nhu cầu vượt 52
            total_demand = random.randint(total_capacity_per_hour + 1, total_capacity_per_hour + 8) 
            # Phân bổ ngẫu nhiên giữa đến và đi, nhưng đảm bảo mỗi loại đều có số lượng hợp lý
            num_arrivals = random.randint(25, 30)
            num_departures = total_demand - num_arrivals
        else: # Giờ thấp điểm
            num_arrivals = random.randint(15, 22)
            num_departures = random.randint(15, 22)

        # Tạo các chuyến bay đến
        for _ in range(num_arrivals):
            flight_data.append([
                flight_id_counter, f"{random.choice(list(airlines.keys()))}{random.randint(100, 9999)}",
                random.choice(all_airports), 'VVTS', random.choice(list(airlines.values())),
                f"{hour:02d}:{random.randint(0, 59):02d}"
            ])
            flight_id_counter += 1
        
        # Tạo các chuyến bay đi
        for _ in range(num_departures):
            flight_data.append([
                flight_id_counter, f"{random.choice(list(airlines.keys()))}{random.randint(100, 3999)}",
                'VVTS', random.choice(all_airports), random.choice(list(airlines.values())),
                f"{hour:02d}:{random.randint(0, 59):02d}"
            ])
            flight_id_counter += 1

    df_schedule = pd.DataFrame(flight_data, columns=['flight_id', 'callsign', 'origin', 'destination', 'aircraft_type', 'eobt'])
    df_schedule = df_schedule.sort_values(by='eobt').reset_index(drop=True)
    df_schedule['flight_id'] = df_schedule.index + 1
    
    df_schedule.to_csv('vvts_schedule.csv', index=False)
    print(f"File 'vvts_schedule.csv' đã được tạo thành công với {len(df_schedule)} chuyến bay.")

def generate_eet_data():
    """Tạo dữ liệu thời gian bay dự kiến (EET)."""
    eet_data = [['VVNB', 100], ['VVDN', 60], ['VVCR', 45], ['VVPQ', 40], ['VVDL', 35], ['VVBM', 35], ['VVTH', 80], ['VVCI', 105], ['VTBS', 75], ['WSSS', 105], ['VHHH', 150], ['WMKK', 110], ['RKSI', 280], ['RJTT', 330], ['RPLL', 160]]
    df_eets = pd.DataFrame(eet_data, columns=['origin', 'eet_minutes'])
    df_eets.to_csv('eets.csv', index=False)
    print("File 'eets.csv' đã được tạo thành công.")

if __name__ == "__main__":
    generate_holistic_flight_schedule()
    generate_eet_data()
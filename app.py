import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import os

# --- Cấu hình trang và Hằng số ---
st.set_page_config(page_title="ATFM Simulation Dashboard", layout="wide")

VVTS_CONFIG = {
    "total_capacity_hourly": 52,
    "taxi_out_time_minutes": 15
}

# --- Các hàm xử lý (Core Logic) ---
@st.cache_data
def load_data():
    """Tải dữ liệu từ các file CSV."""
    try:
        script_dir = os.path.dirname(os.path.realpath(__file__))
        schedule_path = os.path.join(script_dir, 'vvts_schedule.csv')
        eets_path = os.path.join(script_dir, 'eets.csv')
        flights_df = pd.read_csv(schedule_path)
        eets_df = pd.read_csv(eets_path)
        flights_df['eobt_dt'] = pd.to_datetime(flights_df['eobt'], format='%H:%M').dt.time
        return flights_df, eets_df
    except FileNotFoundError:
        return None, None

def calculate_initial_schedules(flights_df, eets_df):
    """Tính toán lịch trình ban đầu cho cả chuyến đi và đến."""
    today = datetime.now().date()
    # Chuyến đến
    arrivals_df = flights_df[flights_df['destination'] == 'VVTS'].copy()
    arrivals_df = pd.merge(arrivals_df, eets_df, on='origin', how='left')
    arrivals_df['eet_minutes'].fillna(60, inplace=True)
    arrivals_df['eet_delta'] = pd.to_timedelta(arrivals_df['eet_minutes'], unit='m')
    arrivals_df['eobt_dt_full'] = arrivals_df['eobt_dt'].apply(lambda t: datetime.combine(today, t))
    arrivals_df['eldt_dt'] = arrivals_df['eobt_dt_full'] + pd.to_timedelta(VVTS_CONFIG['taxi_out_time_minutes'], unit='m') + arrivals_df['eet_delta']
    
    # Chuyến đi
    departures_df = flights_df[flights_df['origin'] == 'VVTS'].copy()
    departures_df['eobt_dt_full'] = departures_df['eobt_dt'].apply(lambda t: datetime.combine(today, t))
    departures_df['etot_dt'] = departures_df['eobt_dt_full'] + pd.to_timedelta(VVTS_CONFIG['taxi_out_time_minutes'], unit='m')

    return arrivals_df, departures_df

def run_gdp_simulation_for_total_capacity(initial_arrivals_df, initial_departures_df):
    """Áp dụng GDP dựa trên tổng năng lực 52 chuyến/giờ."""
    regulated_schedule = initial_arrivals_df.copy()
    regulated_schedule['cldt_dt'] = regulated_schedule['eldt_dt']
    regulated_schedule['atfm_delay_minutes'] = 0.0
    regulated_schedule['is_regulated'] = False
    
    for hour in range(24):
        # Tính nhu cầu hiện tại dựa trên lịch trình đã có thể bị thay đổi
        arr_demand_this_hour = len(regulated_schedule[regulated_schedule['cldt_dt'].dt.hour == hour])
        dep_demand_this_hour = len(initial_departures_df[initial_departures_df['etot_dt'].dt.hour == hour])
        total_demand_this_hour = arr_demand_this_hour + dep_demand_this_hour

        if total_demand_this_hour > VVTS_CONFIG['total_capacity_hourly']:
            num_to_delay = int(total_demand_this_hour - VVTS_CONFIG['total_capacity_hourly'])
            
            # Ưu tiên trì hoãn các chuyến bay đến trong giờ này
            arrival_flights_in_hour = regulated_schedule[regulated_schedule['cldt_dt'].dt.hour == hour].sort_values(by='cldt_dt')
            flights_to_delay = arrival_flights_in_hour.head(num_to_delay)
            
            if not flights_to_delay.empty:
                # Đẩy các chuyến bay này sang đầu giờ tiếp theo
                next_hour_start_time = pd.to_datetime(f"{hour+1 if hour < 23 else 23}:00").replace(year=datetime.now().year, month=datetime.now().month, day=datetime.now().day, minute=0)
                if hour == 23: # Xử lý trường hợp giờ cuối cùng trong ngày
                     next_hour_start_time += timedelta(days=1)

                delay_interval = timedelta(minutes=2)
                current_delay_time = next_hour_start_time

                for index, flight in flights_to_delay.iterrows():
                    new_cldt = current_delay_time
                    delay = (new_cldt - flight['eldt_dt']).total_seconds() / 60
                    
                    regulated_schedule.loc[index, 'cldt_dt'] = new_cldt
                    regulated_schedule.loc[index, 'atfm_delay_minutes'] = delay
                    regulated_schedule.loc[index, 'is_regulated'] = True
                    current_delay_time += delay_interval
    return regulated_schedule

# --- Giao diện ---
if 'simulation_run' not in st.session_state:
    st.session_state.simulation_run = False

st.title("ATFM Simulation Dashboard - Tan Son Nhat International Airport (VVTS)")

flights_df, eets_df = load_data()
if flights_df is None:
    st.error("Không tìm thấy file dữ liệu. Vui lòng chạy 'generate_data.py' và tải lại trang.")
else:
    placeholder = st.empty()
    with placeholder.container():
        st.header("1. Phân tích Nhu cầu Tổng hợp Ban đầu")
        
        if not st.session_state.simulation_run:
            initial_arrivals_df, initial_departures_df = calculate_initial_schedules(flights_df, eets_df)
            st.session_state.initial_arrivals = initial_arrivals_df
            st.session_state.initial_departures = initial_departures_df
        else:
            initial_arrivals_df = st.session_state.initial_arrivals
            initial_departures_df = st.session_state.initial_departures
        
        arr_demand = initial_arrivals_df.groupby(initial_arrivals_df['eldt_dt'].dt.hour).size()
        dep_demand = initial_departures_df.groupby(initial_departures_df['etot_dt'].dt.hour).size()
        total_demand = (arr_demand.add(dep_demand, fill_value=0)).reindex(range(24), fill_value=0)
        
        overload_hours = total_demand[total_demand > VVTS_CONFIG['total_capacity_hourly']]
        
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=total_demand.index, y=total_demand.values, name='Tổng nhu cầu (Đến + Đi)',
            marker_color=['red' if h in overload_hours.index else 'cornflowerblue' for h in total_demand.index]
        ))
        fig.add_hline(y=VVTS_CONFIG['total_capacity_hourly'], line_dash="dash", line_color="black", annotation_text=f"Năng lực ({VVTS_CONFIG['total_capacity_hourly']})")
        fig.update_layout(title='Tổng Nhu cầu Hoạt động vs. Năng lực Sân bay', xaxis_title='Giờ trong ngày (UTC)', yaxis_title='Số lượt cất/hạ cánh', plot_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig, use_container_width=True)

        if not overload_hours.empty:
            st.warning(f"Phát hiện nguy cơ quá tải năng lực tổng hợp tại các khung giờ: {', '.join(map(str, overload_hours.index))}h.")
            if st.button("Áp dụng Chương trình Điều tiết (GDP)"):
                st.session_state.regulated_schedule = run_gdp_simulation_for_total_capacity(initial_arrivals_df, initial_departures_df)
                st.session_state.simulation_run = True
                placeholder.empty()
        else:
            st.success("Không phát hiện nguy cơ quá tải trong ngày.")

    if st.session_state.simulation_run:
        st.header("2. Kết quả và Phân tích sau Điều tiết")
        
        # Tính toán lại nhu cầu sau điều tiết
        initial_arr_demand = st.session_state.initial_arrivals.groupby(st.session_state.initial_arrivals['eldt_dt'].dt.hour).size()
        initial_dep_demand = st.session_state.initial_departures.groupby(st.session_state.initial_departures['etot_dt'].dt.hour).size()
        initial_total_demand = (initial_arr_demand.add(initial_dep_demand, fill_value=0)).reindex(range(24), fill_value=0)

        regulated_arr_demand = st.session_state.regulated_schedule.groupby(st.session_state.regulated_schedule['cldt_dt'].dt.hour).size()
        regulated_total_demand = (regulated_arr_demand.add(initial_dep_demand, fill_value=0)).reindex(range(24), fill_value=0)

        compare_df = pd.DataFrame({'Nhu cầu Ban đầu': initial_total_demand, 'Nhu cầu Sau Điều tiết': regulated_total_demand})
        
        fig_compare = go.Figure()
        fig_compare.add_trace(go.Bar(x=compare_df.index, y=compare_df['Nhu cầu Ban đầu'], name='Nhu cầu Ban đầu (Tắc nghẽn)', marker_color='red'))
        fig_compare.add_trace(go.Bar(x=compare_df.index, y=compare_df['Nhu cầu Sau Điều tiết'], name='Nhu cầu Sau Điều tiết (An toàn)', marker_color='green'))
        fig_compare.add_hline(y=VVTS_CONFIG['total_capacity_hourly'], line_dash="dash", line_color="black", annotation_text=f"Năng lực ({VVTS_CONFIG['total_capacity_hourly']})")
        fig_compare.update_layout(barmode='group', title='So sánh Hiệu quả Điều tiết Tổng hợp', xaxis_title='Giờ trong ngày (UTC)', yaxis_title='Số lượt cất/hạ cánh', plot_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig_compare, use_container_width=True)

        regulated_flights = st.session_state.regulated_schedule[st.session_state.regulated_schedule['is_regulated']].copy()
        if not regulated_flights.empty:
            st.subheader("Thống kê chung")
            col1, col2, col3 = st.columns(3)
            col1.metric("Số chuyến bay bị điều tiết", f"{len(regulated_flights)}")
            total_delay = regulated_flights['atfm_delay_minutes'].sum()
            col2.metric("Tổng thời gian trễ", f"{int(total_delay)} phút")
            max_delay = regulated_flights['atfm_delay_minutes'].max()
            col3.metric("Chuyến bay trễ nhiều nhất", f"{int(max_delay)} phút")
            
            st.subheader("Danh sách chi tiết các chuyến bay đến bị điều tiết")
            regulated_flights['eldt_initial_str'] = regulated_flights['eldt_dt'].dt.strftime('%H:%M:%S')
            regulated_flights['cldt_new_str'] = regulated_flights['cldt_dt'].dt.strftime('%H:%M:%S')
            regulated_flights['ctot_new_str'] = regulated_flights.apply(lambda row: (row['cldt_dt'] - row['eet_delta'] - pd.to_timedelta(VVTS_CONFIG['taxi_out_time_minutes'], unit='m')).strftime('%H:%M:%S'), axis=1)
            regulated_flights['atfm_delay_minutes'] = regulated_flights['atfm_delay_minutes'].round().astype(int)
            display_cols = ['callsign', 'origin', 'eobt', 'eldt_initial_str', 'atfm_delay_minutes', 'ctot_new_str', 'cldt_new_str']
            st.dataframe(regulated_flights[display_cols].rename(columns={'callsign': 'Tên hiệu', 'origin': 'Sân bay đi', 'eobt': 'EOBT Gốc', 'eldt_initial_str': 'ELDT Gốc', 'atfm_delay_minutes': 'Phút trễ', 'ctot_new_str': 'CTOT Mới', 'cldt_new_str': 'CLDT Mới'}), use_container_width=True)
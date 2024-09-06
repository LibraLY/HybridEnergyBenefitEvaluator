import streamlit as st
import pandas as pd
from concurrent.futures import ProcessPoolExecutor, as_completed
import datetime

st.set_page_config(
    page_title="光热与风电光伏一体化项目收益测算系统",
    page_icon="🔋",
    # layout="wide"
)


@st.cache_data
def load_gbk(file):
    data = pd.read_csv(file, encoding='gbk')
    return data


@st.cache_data
def load_utf8(file):
    data = pd.read_csv(file)
    return data


def process_row(row):
    # 这里可以添加你想要的操作
    row['补燃电量'] = 0
    row['光热理论出力'] = row['光热'] * solar_thermal
    row['风电理论出力'] = row['风电出力'] * wind_power
    row['光伏理论出力'] = row['光伏出力'] * photovoltaic

    if row['网供负荷-归一化'] >= (
            row['风电理论出力'] + row['光伏理论出力'] + 100 * solar_thermal) / max_combined_output:
        if stored_heat[0] >= 100 * solar_thermal:
            row['综合出力'] = row['风电理论出力'] + row['光伏理论出力'] + 100 * solar_thermal
            row['储热量'] = stored_heat[0]
            stored_heat[0] = stored_heat[0] - 100 * solar_thermal + row['光热理论出力']
            row['光热实际出力'] = 100 * solar_thermal
        else:
            row['综合出力'] = row['风电理论出力'] + row['光伏理论出力'] + stored_heat[0]
            row['储热量'] = stored_heat[0]
            row['光热实际出力'] = stored_heat[0]
            stored_heat[0] = row['光热理论出力']
            if fire:
                if row['is_between_17_and_22']:
                    row['补燃电量'] = 100 * solar_thermal - row['储热量']
                    row['综合出力'] = row['风电理论出力'] + row['光伏理论出力'] + 100 * solar_thermal

        row['弃风光量'] = 0
        row['弃风量'] = 0
        row['弃光量'] = 0
        row['电加热量'] = 0
        row['风电实际出力'] = row['风电理论出力']
        row['光伏实际出力'] = row['光伏理论出力']
    else:
        if row['网供负荷-归一化'] >= (row['风电理论出力'] + row['光伏理论出力']) / max_combined_output:
            row['综合出力'] = row['网供负荷-归一化'] * max_combined_output
            row['弃风光量'] = 0
            if stored_heat[0] - (row['综合出力'] - row['风电理论出力'] - row['光伏理论出力']) >= 0:
                row['光热实际出力'] = row['综合出力'] - row['风电理论出力'] - row['光伏理论出力']
                row['储热量'] = stored_heat[0]
                stored_heat[0] = stored_heat[0] - row['光热实际出力'] + row['光热理论出力']
            else:
                row['综合出力'] = row['风电理论出力'] + row['光伏理论出力'] + stored_heat[0]
                row['光热实际出力'] = stored_heat[0]
                row['储热量'] = stored_heat[0]
                stored_heat[0] = row['光热理论出力']
                if fire:
                    if row['is_between_17_and_22']:
                        row['补燃电量'] = row['网供负荷-归一化'] * max_combined_output - row['风电理论出力'] - row[
                            '光伏理论出力'] - row['储热量']
                        row['综合出力'] = row['网供负荷-归一化'] * max_combined_output
            row['电加热量'] = 0
        else:
            if on:
                if (row['风电理论出力'] + row['光伏理论出力'] - row[
                    '网供负荷-归一化'] * max_combined_output) > 100 * solar_thermal * electric_heater_scale:
                    row['综合出力'] = row['网供负荷-归一化'] * max_combined_output
                    row['储热量'] = stored_heat[0]
                    stored_heat[0] = stored_heat[0] + row[
                        '光热理论出力'] + 100 * solar_thermal * electric_heater_scale * heater_module_efficiency
                    row['弃风光量'] = row['风电理论出力'] + row['光伏理论出力'] - row[
                        '网供负荷-归一化'] * max_combined_output - 100 * solar_thermal * electric_heater_scale
                    row['电加热量'] = 100 * solar_thermal * electric_heater_scale
                else:
                    row['综合出力'] = row['网供负荷-归一化'] * max_combined_output
                    row['储热量'] = stored_heat[0]
                    stored_heat[0] = stored_heat[0] + row['光热理论出力'] + (
                            row['风电理论出力'] + row['光伏理论出力'] - row[
                        '网供负荷-归一化'] * max_combined_output) * heater_module_efficiency
                    row['弃风光量'] = 0
                    row['电加热量'] = row['风电理论出力'] + row['光伏理论出力'] - row[
                        '网供负荷-归一化'] * max_combined_output

            else:
                if row['风电理论出力'] + row['光伏理论出力'] > max_combined_output:
                    row['综合出力'] = row['网供负荷-归一化'] * max_combined_output + (
                            1 - curtailment_factor) * (max_combined_output - row[
                        '网供负荷-归一化'] * max_combined_output)
                    row['储热量'] = stored_heat[0]
                    stored_heat[0] = stored_heat[0] + row['光热'] * solar_thermal
                    row['弃风光量'] = curtailment_factor * (
                            max_combined_output - row['网供负荷-归一化'] * max_combined_output) + (
                                              row['风电出力'] * wind_power + row[
                                          '光伏出力'] * photovoltaic - max_combined_output)
                else:
                    row['综合出力'] = row['网供负荷-归一化'] * max_combined_output + (
                            1 - curtailment_factor) * (
                                              row['风电出力'] * wind_power + row['光伏出力'] * photovoltaic -
                                              row['网供负荷-归一化'] * max_combined_output)
                    row['储热量'] = stored_heat[0]
                    stored_heat[0] = stored_heat[0] + row['光热'] * solar_thermal
                    row['弃风光量'] = curtailment_factor * (
                            row['风电出力'] * wind_power + row['光伏出力'] * photovoltaic - row[
                        '网供负荷-归一化'] * max_combined_output)
                row['电加热量'] = 0
            row['光热实际出力'] = 0

        if row['风电出力'] == 0:
            row['弃风量'] = 0
            row['弃光量'] = row['弃风光量']
            row['风电实际出力'] = row['风电理论出力']
            row['光伏实际出力'] = row['光伏理论出力'] - row['弃光量'] - row['电加热量']
        elif row['光伏出力'] == 0:
            row['弃风量'] = row['弃风光量']
            row['弃光量'] = 0
            row['风电实际出力'] = row['风电理论出力'] - row['弃风量'] - row['电加热量']
            row['光伏实际出力'] = row['光伏理论出力']
        else:
            row['弃风量'] = row['弃风光量'] * row['风电理论出力'] / (row['风电理论出力'] + row['光伏理论出力'])
            row['弃光量'] = row['弃风光量'] * row['光伏理论出力'] / (row['风电理论出力'] + row['光伏理论出力'])
            row['风电实际出力'] = row['风电理论出力'] - row['弃风量'] - row['电加热量'] * row['风电理论出力'] / (
                    row['风电理论出力'] + row['光伏理论出力'])
            row['光伏实际出力'] = row['光伏理论出力'] - row['弃光量'] - row['电加热量'] * row['光伏理论出力'] / (
                    row['风电理论出力'] + row['光伏理论出力'])

    if stored_heat[0] > 100 * solar_thermal * solar_thermal_storage_duration:
        row['弃热量'] = stored_heat[0] - 100 * solar_thermal * solar_thermal_storage_duration
        stored_heat[0] = 100 * solar_thermal * solar_thermal_storage_duration
    else:
        row['弃热量'] = 0
    return row


def apply_concurrently(df, func, num_workers=None):
    if num_workers is None:
        num_workers = min(32, (len(df) + 4) // 5)  # 合理选择工作者数量

    with ProcessPoolExecutor(max_workers=num_workers) as executor:
        futures = [executor.submit(func, row) for _, row in df.iterrows()]

        processed_rows = []
        for future in as_completed(futures):
            processed_rows.append(future.result())

    return pd.DataFrame(processed_rows, columns=df.columns)


st.title('光热与风电光伏一体化项目收益测算系统')

df = load_utf8('2023年负荷数据.csv')
df_ba = load_gbk('巴彦淖尔电价数据.csv')
df_a = load_gbk('阿拉善电价数据.csv')
df_e = load_gbk('鄂尔多斯电价数据.csv')
names_ba = list(df_ba.keys())
names_a = list(df_a.keys())
names_e = list(df_e.keys())
with st.form("my_form"):
    st.write("项目规模（十万千瓦）")
    col1, col2, col3 = st.columns(3)
    with col1:
        solar_thermal = st.number_input("光热", value=2.0)

    with col2:
        wind_power = st.number_input("风电", value=3.0)

    with col3:
        photovoltaic = st.number_input("光伏", value=2.0)

    col1, col2 = st.columns(2)
    with col1:
        region = st.selectbox(
            "地级市",
            ("鄂尔多斯", "巴彦淖尔", "阿拉善"),
            index=None,
            placeholder="选择城市...",
        )
        st.form_submit_button('确定')

    with col2:
        if region == "巴彦淖尔":
            project_region = st.selectbox(
                "旗县",
                ("乌拉特前旗", "乌拉特中旗", "乌拉特后旗", "磴口县"),
                index=None,
                placeholder="选择旗县...",
                # label_visibility="collapsed"
            )
            grid_node = st.selectbox(
                "电网节点",
                names_ba,
                index=None,
                placeholder="选择节点...",
            )
            if grid_node:
                df['节点'] = df_ba[grid_node]
        elif region == "鄂尔多斯":
            project_region = st.selectbox(
                "旗县",
                ("达拉特旗", "杭锦旗", "乌审旗", "鄂托克旗", "鄂托克前旗"),
                index=None,
                placeholder="选择旗县...",
                # label_visibility="collapsed"
            )
            grid_node = st.selectbox(
                "电网节点",
                names_e,
                index=None,
                placeholder="选择节点...",
            )
            if grid_node:
                df['节点'] = df_e[grid_node]
        elif region == "阿拉善":
            project_region = st.selectbox(
                "旗县",
                ("阿左旗", "阿右旗", "额济纳旗"),
                index=None,
                placeholder="选择旗县...",
                # label_visibility="collapsed"
            )
            grid_node = st.selectbox(
                "电网节点",
                names_a,
                index=None,
                placeholder="选择节点...",
            )
            if grid_node:
                df['节点'] = df_a[grid_node]

    solar_thermal_storage_duration = st.number_input("光热储热时长(h)", value=6)

    on = st.toggle("是否设置电加热", value=True)

    col1, col2 = st.columns(2)
    with col1:
        heater_module_efficiency = st.number_input("电加热器效率", value=0.45)
        curtailment_factor = st.number_input("弃风弃光因子%", value=10)
        curtailment_factor = curtailment_factor / 100
    with col2:
        electric_heater_scale = st.number_input("电加热器规模%", value=50)
        electric_heater_scale = electric_heater_scale / 100

    fire = st.toggle("是否设置补燃", value=True)
    stored_heat = [0]
    high_time = st.number_input("晚高峰时长（h）", value=5)
    max_combined_output = st.number_input("最大综合出力", value=300)
    but = st.form_submit_button('计算')
    df['时间'] = pd.to_datetime(df['时间'])
    df['hour'] = df['时间'].dt.hour
    if high_time == 6:
        df['is_between_17_and_22'] = (df['hour'] >= 17) & (df['hour'] <= 22)
    elif high_time == 5:
        df['is_between_17_and_22'] = (df['hour'] >= 17) & (df['hour'] <= 21)

if but:
    df_p = load_utf8(f'{project_region}.csv')
    df['风电出力'] = df_p['风电出力（MW）']
    df['光伏出力'] = df_p['光伏出力（MW）']
    df['光热'] = df_p['光热出力（MW）']

    df['网供负荷-归一化'] = df['全网_全网网供'] / df['全网_全网网供'].max()
    df['弃风光量'] = 0

    df = df.apply(process_row, axis=1)
    df['综合出力-归一化'] = df['综合出力'] / max_combined_output
    new_order = ['时间', '光热理论出力', '风电理论出力', '光伏理论出力', '光热实际出力', '风电实际出力', '光伏实际出力',
                 '储热量', '电加热量', '补燃电量',
                 '弃风量', '弃光量', '弃风光量', '弃热量', '全网_全网网供', '网供负荷-归一化', '综合出力',
                 '综合出力-归一化']
    df_reordered = df.loc[:, new_order]
    st.write(df_reordered)
    load_coverage_rate_1 = df['综合出力-归一化'].sum() / df['网供负荷-归一化'].sum()
    st.write("负荷保障率1:", round(load_coverage_rate_1 * 100, 2), "%")

    selected_columns = ['网供负荷-归一化', '综合出力-归一化']
    load_coverage_rate_2 = df[selected_columns].min(axis=1).sum() / df['网供负荷-归一化'].sum()
    st.write("负荷保障率2:", round(load_coverage_rate_2 * 100, 2), "%")

    annual_trading_volume = df['综合出力'].sum()
    st.write("全年交易电量：", round(annual_trading_volume, 4), '（MWh）')

    annual_abandoned_energy = df['弃风光量'].sum() + df['弃热量'].sum()
    st.write("全年弃电量：", round(annual_abandoned_energy, 4), '（MWh）')

    electricity_trading_profit = df.apply(lambda profit: profit['节点'] * profit['综合出力'], axis=1).sum()
    st.write("电量交易收益：", round(electricity_trading_profit / 10000, 4), '（万元）')

    annual_solar_thermal_output = df['光热实际出力'].sum()
    st.write("全年光热总出力：", round(annual_solar_thermal_output, 4), '（MWh）')

    annual_wind_power_output = df['风电实际出力'].sum()
    st.write("全年风电总出力：", round(annual_wind_power_output, 4), '（MWh）')

    annual_solar_power_output = df['光伏实际出力'].sum()
    st.write("全年光伏总出力：", round(annual_solar_power_output, 4), '（MWh）')

    annual_electric_heating_output = df['电加热量'].sum()
    st.write("全年总电加热量：", round(annual_electric_heating_output, 4), '（MWh）')

    annual_abandoned_heat_power = df['弃热量'].sum()
    st.write("全年总弃热电量：", round(annual_abandoned_heat_power, 4), '（MWh）')

    annual_supplementary_firing_power = df['补燃电量'].sum()
    st.write("全年总补燃电量：", round(annual_supplementary_firing_power, 4), '（MWh）')

    df['光热实际出力'] = df['光热实际出力'] / max_combined_output
    df['风电实际出力'] = df['风电实际出力'] / max_combined_output
    df['光伏实际出力'] = df['光伏实际出力'] / max_combined_output
    df['电加热量'] = df['电加热量'] / max_combined_output
    df['弃风量'] = df['弃风量'] / max_combined_output
    df['弃光量'] = df['弃光量'] / max_combined_output
    df['弃风光量'] = df['弃风光量'] / max_combined_output
    df['弃热量'] = df['弃热量'] / max_combined_output
    df['补燃电量'] = df['补燃电量'] / max_combined_output

    if "df" not in st.session_state:
        st.session_state.df = df
    st.session_state.df = df

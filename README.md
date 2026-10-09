# 大阪天气日历（iPhone 自带日历）

免费 ICS 订阅日历，每天自动更新大阪市天气，显示天气图标、天气描述、最高气温和最低气温，覆盖过去 15 天至未来 15 天。

## 订阅地址

`https://raw.githubusercontent.com/GitHubsyousyou/osaka-weather-calendar/main/osaka-weather.ics`

在 iPhone 上打开“设置 → App → 日历 → 日历账户 → 添加账户 → 添加已订阅的日历”，粘贴上面的 URL 并保存。不同 iOS 版本菜单名称可能略有不同。也可以在日历账户中添加订阅日历。

## 数据说明

- 过去日期使用 Open-Meteo 历史再分析数据；这是模型再分析估算，不是气象台观测站原始实测记录。
- 今天和未来日期使用 Open-Meteo 天气预报。
- 位置固定为大阪市中心附近坐标，单位为摄氏度，不需要 API 密钥。
- GitHub Actions 计划每天日本时间 09:20 更新日历文件；iPhone 实际刷新订阅的时间由 iOS 控制。

## 自动更新

仓库中的 GitHub Actions 工作流会每日生成 `osaka-weather.ics` 并提交更新。首次运行后，以上订阅链接才会有完整天气内容。
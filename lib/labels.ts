// All user-facing Chinese strings. Structured for future i18n.

export const labels = {
  brand: '瑞幸咖啡 · 北美',
  appTitle: '门店运营看板',

  nav: {
    home: '门店看板',
    preview: '看板预览',
    efficiency: '效能看板',
  },

  filter: {
    dateRange: '日期范围',
    from: '开始',
    to: '结束',
    city: '城市',
    region: '区域',
    store: '门店',
    all: '全部',
    apply: '应用',
    reset: '重置',
    exportData: '导出数据',
    rangeNoteOutside: '所选日期超出数据保留窗口，自动夹取至最近可用范围。',
    rangeNoteEmpty: '所选日期范围无运营数据。',
  },

  groups: {
    business: '业务量',
    efficiency: '效率',
    quality: '品质',
  },

  comparison: {
    wow: '周同比',
    mom: '月同比',
    sequential: '环比',
    noData: '—',
  },

  freshness: {
    updatedJustNow: '数据刚刚更新',
    updatedAgo: (mins: number) => `数据更新于 ${mins} 分钟前`,
    stale: '· 显示历史数据',
  },

  pending: '数据源待接入',

  table: {
    city: '城市',
    region: '区域',
    store: '门店',
    avgDailyProducts: '单店日均商品数',
    avgDailyFreshMade: '单店日均现制商品数',
    avgDailyEquiv: '单店日均等效商品数',
    satisfaction: '满意度',
    hourlyCups: '小时杯量',
    perfHourlyCups: '绩效小时杯量',
    hourlyCupAchieve: '小时杯量达成比',
    qcPassRate: '品控稽核达标率',
    qcAvgScore: '品控稽核平均分',
    materialLossRate: '原料损耗率',
    efficiencyDuration: '效能时长',
    orderCount: '订单数量',
    pickupCount: '自取订单数',
    deliveryCount: '外送订单数',
    productCount: '商品数量',
    freshMadeCount: '现制商品数',
    totals: '汇总 / 平均',
    nonOperating: '-',
    noOperatingStores: '所选筛选下无运营门店',
    exportXlsx: '导出 Excel',
    exportCsv: '导出 CSV',
    sortAsc: '升序',
    sortDesc: '降序',
  },

  efficiency: {
    chartTitle: '当日效能曲线',
    chartHint: '突出显示当日峰值时段',
    tableTitle: '半小时效能明细',
    acceptResponse: '单均接单响应时长',
    makeDuration: '平均等效制作时长',
    totalDuration: '效能时长',
    slot: '时段',
    orderCount: '订单数',
    equivCount: '等效商品数',
  },

  preview: {
    title: '看板预览',
    subtitle: '关键指标速览（用于截图与展示）',
  },

  charts: {
    orderType: '订单类型占比',
    orderTypeSubtitle: '自取 vs 外卖订单分布',
    productSales: '商品销售情况',
    productSalesSubtitle: '现制 vs 外购商品分布',
    pickup: '自取',
    delivery: '外卖',
    freshMade: '现制',
    purchased: '外购',
    topSpu: '商品 TOP10',
    topSpuSubtitle: '所选范围内销量最高的商品',
    spuName: '商品名称',
    spuQuantity: '商品数量',
    spuShare: '数量占比',
    legendRawCounts: (n: number) => `（共 ${n.toLocaleString('en-US')} 件）`,
  },

  intervalSales: {
    title: '区间销售明细',
    subtitle: '所选日期范围内分时段汇总',
    slot: '时段',
    delivery: '外送订单数',
    pickup: '自取订单数',
    freshMade: '现制商品数',
    purchased: '外购商品数',
  },

  intervalEfficiency: {
    title: '区间效能明细',
    subtitle: '分时段效能耗时（加权平均）',
    slot: '时段',
    accept: '单均接单响应时长',
    make: '平均等效制作时长',
    total: '效能时长',
  },

  exportGate: {
    title: '完整导出受限',
    body: '完整导出需要授权口令，当前视图导出无需登录。',
    inputPlaceholder: '请输入口令',
    confirm: '确认',
    cancel: '取消',
    error: '口令错误',
  },

  unitsHint: {
    percent: '%（保留两位小数）',
    count: '件 / 单',
    score: '分（满分 100）',
    duration: '秒（加权平均）',
  },
} as const;

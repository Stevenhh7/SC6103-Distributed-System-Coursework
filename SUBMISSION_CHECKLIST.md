# 正式提交与演示检查（2026-10-13）

依据课程四页 PDF 及老师最新通知。详细需求映射见 [最终审核](FINAL_AUDIT_20261013.md)。

- [x] 六项业务、UDP、手工编解码、请求/回复丢失、ALO/AMO、重传及多客户端回调已实现。
- [x] 独立解压源码复核：200 项测试、16 项本机 UDP 实验全部通过；实际 Java 17 运行时。
- [x] 10 月 12 日三机预演完成；原始 A/B 日志、28 张截图和 94 项证据核对保留。
- [x] 封面三人正式姓名、各 33.33% 已填写。精确比例各三分之一，显示总和99.99%来自舍入。
- [x] 封面演示预约：slot 11，2026-10-17，14:15-14:30，LT8，Singapore time。

## 10 月 14 日截止的提交

| 材料 | 谁提交 | 内容 | 当前状态 |
|---|---|---|---|
| Lab report | 全组一名代表交1份 | `output/pdf/SC6103_Project_Report.pdf` | 已准备，NTULearn提交未核实 |
| Source code | 全组一名代表交1个ZIP | 全部Java/Python源码、构建/运行说明、测试及证据 | 完整源码打包，NTULearn提交未核实 |
| Peer evaluation - Zhang Zhiyin | Zhang本人 | NTULearn正式表格，填写自己和另外两人 | 必须本人提交，未核实 |
| Peer evaluation - Peng Jinyu | Peng本人 | 同上 | 必须本人提交，未核实 |
| Peer evaluation - Ji Chengyu | Ji本人 | 同上 | 必须本人提交，未核实 |

**互评表每人必交，不能用代表的一份表替代三人的提交。** 封面贡献比例不能替代互评表，请各自按老师表格说明完成。

原手册说明源码入口只收一个文件，且不允许重新提交。不要将仅含报告素材的 `SC6103_Report_Editable_Package.zip` 当作源码包，也不要只交 GitHub 链接。原 PDF 要求截止日午夜前；以 NTULearn 入口具体时间为准，提前提交。

- [ ] 小组代表上传报告，检查提交成功记录。
- [ ] 小组代表上传完整源码 ZIP，检查提交成功记录。
- [ ] Zhang Zhiyin 提交自己的 peer evaluation form。
- [ ] Peng Jinyu 提交自己的 peer evaluation form。
- [ ] Ji Chengyu 提交自己的 peer evaluation form。

## 10 月 17 日现场演示

- [x] [报名表](https://docs.google.com/spreadsheets/d/1AiNb86SMPOP1NyYXTh8I7USKg1epzmb3PgcVq9U9JeM/edit) 的 slot 11 已登记三人；10月13日读取核对，用户确认。
- [ ] 三人均到 LT8，建议 **14:00** 准备，正式时段 **14:15-14:30**。
- [ ] 带三台自用电脑、电源和最终代码：一台Java服务器、两台Python客户端。
- [ ] 现场重新查IPv4并验证UDP；`10.91.127.7`是预演地址，不保证当天相同。
- [ ] 演示六业务及错误、订座回调、双监控、过期停止、ALO/AMO非幂等对比；对比间重启复位。
- [ ] 准备解释协议、超时重传、AMO历史、幂等性和回调；老师可能提问。

无需幻灯片，报告没有字数或页数上限。GitHub发布及预演不代表NTULearn提交或正式课堂演示完成。

# 故障排查

## 换了 PDF，旧论文还在

build 始终只扫描 data/seed_papers 本层 PDF，不读取目录外论文来扩大范围。移走旧 PDF 再 build 即排除它，不必删 TEI。status 区分当前输入与最近快照；export/rebuild 只导出最近快照，不同步新 PDF。

## 想从下载目录直接使用

先 `python matrix_tool.py import "下载目录"`，再 build。build 不接受 --input-dir 或 --keep-existing。也可直接手动复制到 seed_papers。

## GROBID 不可达

检查 .env、校园网络或 VPN。已有有效 TEI 不需要 GROBID；也可 import PDF --from-tei XML 后 build。旧缓存无哈希不会因此强制联网；已知 PDF 内容变化时仍须重新解析，避免冒用旧版本。

## 抽取后等待较久

后续在做关系分类和逐句翻译，终端显示批次/句数。有效响应但输出缺失时程序会自动拆小批次、扩大预算后有限补试；低置信标签自动检查一次。网络请求异常会停止本轮连续调用，保存已有结果并继续出表。

检查 .env 的模型地址、认证和模型名，服务恢复后重新 build。HTTP 502 可能来自代理或服务网关，GROBID 可用不代表模型可用。临时出表用 build --no-llm；完全离线且无需同步 PDF 用 export。

## 仍有不确定标签或英文

自动补救有次数和服务条件边界，不通过降低置信阈值或编造结果来清零。保留标记不阻断表格生成，也不要求用户先复核。服务恢复/参数调整后 build 可补未完成项；如主动精修，才使用 export-labels、export-untranslated 等可选工具。

## 清理缓存后 export 报缺少快照

cache clean --all --apply 会删除当前 TEI/JSON。PDF、短名及人工数据仍在，运行 build 即可恢复。默认 clean 只是预览历史解析文件，没加 --apply 不会删除。

## Excel 无法写入

关闭正在 Excel 中打开的目标文件后重试。若构建已经完成、JSON 和模型结果已保存，运行 export 即可重新出表，不需要重新调用模型。

## 首次配置错误

build/import 自动创建缺失配置；可选 init 创建空项目。普通新项目无需旧 HMARS 等 TEI，也不要用 --migrate-legacy。服务连接只写 .env，不在源码中硬编码。

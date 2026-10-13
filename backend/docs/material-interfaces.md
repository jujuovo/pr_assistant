# 五类材料接口与非OCR处理

本阶段仅增加后端接口和无需OCR的处理，不新增前端页面，不实现自动加分，不连接外部学校平台。不修改 `Student` 中的学业/外语成绩、综合成绩或 `Application` 的状态及分数。原有蓝桥杯识别与志愿材料功能保留。

## 五类数据

| category | 板块 | data的主要字段 | 已完成的非OCR处理 |
|---|---|---|---|
| academic | 学业成绩 | term、courses：课程代码/名称/学分/成绩/满分/included | 结构化成绩录入、UTF-8 CSV预览、课程校验、学分加权均分、校方数据对照 |
| competition | 学科竞赛 | competition_name、organizer、competition_level、award_level、award_date；可选certificate_no、project_key | 自主申报类别/等级、编号与来源数据对照、人工核验 |
| language | 外语能力 | exam_name、language、score、full_score、test_date、certificate_no；可选score_scale | 数值/日期校验、考试量尺记录、管理员录入官方核验数据后比较 |
| student_work | 学生工作 | as_of、appointments：organization、position、position_level、start_date、end_date、assessment_result | 任职起止时间校验、任职天数、重叠区间合并、职务级别和考核结果记录 |
| honor | 荣誉称号 | honor_name、honor_level、issuer、award_date；可选certificate_no | 称号/颁发单位/级别标准化、与校方荣誉名册数据对照 |

各类均可提供 `reference_id`，用来精确定位管理员导入的来源记录。没有来源数据时只提示“等待官方数据”，不会判为材料虚假。项目名称、级别及考核结果目前记录原始申报文字，没有自行定义学校的等级映射。

## 通用接口

前缀：`/api/materials`，需要主项目已登录的Session Cookie；错误为JSON，常见状态码400/401/403/404/409。

| 方法 | 路径（在上述前缀下） | 用途 |
|---|---|---|
| GET | /types | 获取五类字段、非OCR能力及尚未启用的识别状态 |
| GET / POST | /{category}/records | 本人/同院材料列表；学生创建结构化材料草稿 |
| GET / PATCH | /{category}/records/{id} | 查询或修改本人草稿/待补充材料 |
| POST | /{category}/records/{id}/attachments | 上传私有附件，multipart字段version、files（可多次同名） |
| GET | /{category}/records/{id}/attachments/{attachment_id} | 本人或同院教师/管理员下载原件 |
| POST | /{category}/records/{id}/submit | 学生提交人工核验 |
| POST | /{category}/records/{id}/withdraw | 学生撤回尚未核验的提交 |
| POST | /{category}/records/{id}/check | 与管理员录入的结构化来源数据对照，并保留当时的来源版本 |
| POST | /{category}/records/{id}/review | 同院教师/管理员人工核验，不产生加分 |
| GET | /{category}/records/{id}/events | 查看创建、编辑、提交、核验、数据对照等审计记录 |
| POST | /{category}/records/{id}/recognize | 预留识别入口：明确返回501及recognition_not_implemented，不运行模型或排队 |
| POST | /academic/parse-csv | 解析成绩CSV并返回预览，不自动保存、认定或写入学生成绩 |
| POST | /sources/import | 本学院管理员批量录入校方/官方核验数据快照 |
| GET | /sources/{source_id} | 同院教师/管理员查看具体来源快照 |
| GET | /openapi.json | 获取本批接口的OpenAPI 3.0文档 |

所有修改、提交、撤回、核验、附件上传和数据对照必须携带当前 `version`。过时版本或非法状态转换返回409；前端需要使用最新响应的version继续操作。

材料状态：`draft → submitted → verified / rejected / needs_correction`。`needs_correction` 可修改后重新提交；`submitted` 可由学生撤回。`verified` 仅代表教师完成材料核验，不代表申请通过或已加分。没有自动删除核验历史的接口。

列表支持 `year`、`student_id`、`status`、`limit`（1至100）、`after_id`；返回 `next_after_id`。教师/管理员只见本学院，学生只见本人。可选关联 `application_id` 必须属于当前学生，材料核验不会改变该申请，关联申请禁止直接删除核验依据。

## 请求示例

创建外语材料（`POST /api/materials/language/records`）：

```json
{
  "year": 2026,
  "data": {
    "exam_name": "CET6",
    "language": "英语",
    "score": 560,
    "full_score": 710,
    "test_date": "2025-12-20",
    "certificate_no": "CET-2025-001",
    "reference_id": "CET-IMPORT-001"
  }
}
```

返回201，包含 `id`、`version`、标准化 `data`、`analysis`、`recognition_status: "not_implemented"` 和 `bonus_result: null`。分数和学分统一返回十进制字符串，拒绝布尔值、NaN、无穷大、负分及超过满分的值。考试满分由申报/来源数据提供，目前不判断通过线、证书有效期或不同考试版本的换算。

修改：`PATCH /api/materials/language/records/1`，请求 `{"version":1,"data":{...完整字段...}}`。这是完整替换data，未提供的可选字段不保留。

提交：`POST /api/materials/language/records/1/submit`，请求 `{"version":2}`。

人工核验：`POST /api/materials/language/records/1/review`，请求 `{"version":3,"decision":"verified","comment":"已核对原件与官方记录"}`。decision允许verified/rejected/needs_correction，说明必填。任何final_score、bonus_score等不在合同内的字段均被拒绝。

管理员导入来源（`POST /api/materials/sources/import`）：

```json
{
  "source_name": "学校核验台账",
  "source_url": "https://school.example.edu/records",
  "records": [{
    "student_id": "学生实际学号",
    "category": "language",
    "year": 2026,
    "external_id": "CET-IMPORT-001",
    "revision": 1,
    "data": {
      "exam_name": "CET6", "language": "英语", "score": 560, "full_score": 710,
      "test_date": "2025-12-20", "certificate_no": "CET-2025-001"
    }
  }]
}
```

这是管理员录入的快照，并非已接通学校平台。来源URL只保存、不主动抓取；未将公开网页当成核验API。整批最多500条；任何一条无效或越学院，整批回滚。相同版本及内容重复导入不重复创建；更改内容须增加revision，旧版本保留。相同编号通过“学院+学生+类别+年度”限定范围，防止跨学生匹配。

数据对照返回 `consistent / mismatch / awaiting_official_data`，始终带 `authenticity: "not_assessed"`，不会自动将材料改为verified。再次导入新来源版本不会覆盖旧核验记录；需显式check才能生成新对照。

## 学业成绩CSV

`POST /api/materials/academic/parse-csv`，multipart字段 `term` 和 `file`。UTF-8或UTF-8 BOM，最多2MB/1000门课程，列严格为：

```csv
course_code,course_name,credits,score,full_score
A,数据结构,2,80,100
B,数学,3,90,100
```

上述均分86、总学分5。先换算每门至100分再按学分加权；只计算included=true的课程。重修、缓考、等级制、课程排除、绩点换算和学校推免口径须另行配置，目前不猜测转换规则。课程代码重复会提示先由教务确认。本接口只预览；需要学生保存为申报材料，或管理员核验后导入来源数据。

## 学生工作统计

as_of明确统计截止日。每条任职记录必须包含单位、职务、职务级别、开始/结束日期和考核结果；仍在任的end_date可为null。天数含首尾日期，不累计as_of以后的日期；多个职务重叠时，各自天数单列，总任职天数按区间并集合并，不重复累计。暂不按“一个月=30天”推断学校规则，不计算干部加分。

## 部署、边界和验证

新增 `material_record`、`material_attachment`、`material_event`、`material_source` 四表。迁移 `20261013_materials` 接在 `20261013_certificate` 后。现有正式数据库使用 `flask --app app db upgrade`（在backend目录），本地SQLite运行 `./start-local.ps1 -PrepareOnly` 即增量建表；保留既有数据。

附件保存于 `backend/private-evidence`，不通过公共uploads地址暴露；每条最多10个，单个10MB，支持PDF、图片、CSV、XLSX；记录SHA-256，下载需权限并设置private/no-store和nosniff。附件仅保存，不证明内容真实；本阶段没有图像质量判断、OCR、文件真实性识别或XLSX内容自动解析。

接口只提供核验数据与基础统计，**没有加分计算、自动写成绩、自动批准申请或跨类别计分去重**。外语成绩上限和考试版本、荣誉/职务等级、比赛级别只做申报和来源对照，认定口径留给后续学校规则。

核心文件：`blueprints/material_bp.py`、`services/materials/`、`material_models.py`。OpenAPI合同：[openapi-materials.json](openapi-materials.json)。回归测试：`tests/test_material_interfaces.py`。

## 后续自动化优先级

基于本项目的数据流判断：学校已有可按学号关联的结构化导出或正式接口时，荣誉称号、学业成绩和学生工作最适合优先实现。学业成绩需要先确定课程及绩点口径；学生工作需要先确定任期和重叠职务认定规则。外语字段较固定，但官方核验接入、考试量尺和版本仍需分别处理。学科竞赛名称、赛级、获奖等级及同项目去重差异较大，适合逐个白名单项目适配。

外语可先提供官方人工核验入口：[中国教育考试网四六级报告单验证](https://www.neea.edu.cn/xhtml1/folder/21033/658-1.htm)。该页面有验证码，不应推断它提供公开自动核验API。学业材料也有[学信网学生成绩验证报告查询](https://www.chsi.com.cn/xlrz/report_gdjycjd.jsp)，校内成绩自动化仍优先采用学校授权的结构化教务数据。


## 复查修复（2026-10-13）

- 新材料关联的旧申请也受本人/同院权限保护：详情、全量列表、待审核列表及审核入口一致；学生不能更换申请所属学生、改审核分数或自行审核通过。未关联新材料的旧接口不是本次全面权限改造范围。
- 课程CSV采用严格解析，表头超限及引号错误均返回400。日期只接受YYYY-MM-DD；拒绝NUL及无效Unicode文字，附件名拒绝控制字符。
- 来源对照排除reference_id和project_key这类定位/处理信息，只比较实际材料字段；缺省与空的可选证书编号及量尺按同一含义对照，兼容旧快照，不改写原始来源或摘要。
- 原件下载前校验大小和SHA-256，校验失败返回409。每次人工核验保留当时的附件编号、名称、大小和SHA-256快照。上传中途写入失败回滚数据库，并清理本次创建的残留文件。

这些修复不启用OCR或加分自动化。

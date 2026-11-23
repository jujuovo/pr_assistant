import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import {
  scoreRows,
  scoreExclusionText,
  scoreStatusText,
  scoreFormulaText,
  formatScoreTime,
  scoreRuleVersions
} from '../src/services/scorePresentation.js'

const source = readFileSync(
  new URL('../src/pages/student/statistics/Statistics.vue', import.meta.url),
  'utf8'
)

test('statistics page is driven only by authoritative workflow snapshot', () => {
  assert.match(source, /workflow\.loadCurrentScore/)
  for (const field of [
    'score.status',
    'candidateScore',
    'includedScore',
    'reason'
  ])
    assert(source.includes(field))
  for (const forbidden of [
    'overrideScore',
    'override_score',
    '人工调整',
    'fetchStatistics',
    'getFacultyScoreSetting',
    '专业排名'
  ])
    assert(!source.includes(forbidden))
})

test('same-work and top-count exclusions remain server explanations', () => {
  const rows = scoreRows({
    entries: [
      {
        id: 1,
        project_source: { type: 'material', id: '7', category: 'competition' },
        candidate_score: '5',
        included_score: '5',
        included: true,
        rule_version_id: 8,
        updated_at: 'now'
      },
      {
        id: 2,
        project_source: { type: 'material', id: '8', category: 'competition' },
        candidate_score: '4',
        included_score: '0',
        included: false,
        exclusion_reason: 'same_work_lower_score'
      },
      {
        id: 3,
        project_source: { type: 'material', id: '9', category: 'competition' },
        candidate_score: '3',
        included_score: '0',
        included: false,
        exclusion_reason: 'max_count_exceeded'
      }
    ]
  })
  assert.deepEqual(
    rows.map((row) => row.reason),
    [undefined, '同一作品仅计最高分', 'max_count_exceeded']
  )
  assert.equal(rows[0].candidateScore, '5')
  assert.equal(rows[1].included, false)
})

test('reconfirmation stays an explicit backend allowed action', () => {
  assert.match(source, /allowedActions\.includes\('confirm_submit'\)/)
  assert.match(source, /materialApi\.reconfirmSubmit/)
  assert.doesNotMatch(source, /automaticScore|estimatedScore/)
})

test('score labels translate state and formula and preserve seconds in Beijing time', () => {
  assert.equal(scoreStatusText('current'), '当前有效')
  assert.equal(scoreStatusText('scored'), '已计分')
  assert.equal(
    scoreFormulaText('academic_score * academic_weight / 100 + academic + comprehensive'),
    '学业基础分 × 学业成绩权重 ÷ 100 + 学术专长计入分 + 综合表现计入分'
  )
  assert.equal(formatScoreTime('2026-11-19T10:34:21.510553Z'), '2026年11月19日 18:34:21')
  assert.equal(formatScoreTime('2026-11-19T18:34:21+08:00'), '2026年11月19日 18:34:21')
  assert.equal(formatScoreTime('2026-11-19T10:34:21'), '2026年11月19日 18:34:21')
  assert.equal(formatScoreTime('invalid'), '—')
  assert.equal(
    scoreRuleVersions({
      rule_version_ids: [-1],
      rule_versions: [{ reference: -1, label: '学业竞赛计分规则（第3版）' }]
    }),
    '学业竞赛计分规则（第3版）'
  )
  assert.doesNotMatch(scoreRuleVersions({ rule_version_ids: [-1] }), /-1/)
  const rows = scoreRows({
    entries: [
      {
        project_source: {
          category: 'competition',
          type: 'material',
          id: '1',
          name: '蓝桥杯省赛二等奖'
        },
        rule_label: '学业竞赛计分规则（第3版）'
      }
    ]
  })
  assert.equal(rows[0].title, '蓝桥杯省赛二等奖')
  assert.equal(rows[0].ruleLabel, '学业竞赛计分规则（第3版）')
})


test('backend score group overrides category guessing, with old student-work fallback', () => {
  const rows = scoreRows({ entries: [
    { project_source: { category: 'student_work' }, score_group: 'comprehensive', included_score: '1.2' },
    { project_source: { category: 'honor' }, score_group: 'comprehensive', included_score: '1' },
    { project_source: { category: 'volunteer' }, score_group: 'academic', included_score: '2' },
    { project_source: { category: 'student_work' }, included_score: '0.8' }
  ] })
  assert.deepEqual(rows.map(row => row.group), ['comprehensive', 'comprehensive', 'academic', 'comprehensive'])
  assert.deepEqual(rows.map(row => row.includedScore), ['1.2', '1', '2', '0.8'])
})


test('competition exclusion reasons are Chinese and preserve server-provided explanations', () => {
  for (const [code, text] of Object.entries({
    same_event_lower_score: '同一赛事同年度仅计最高分',
    same_work_lower_score: '同一作品仅计最高分',
    csp_lower_score: 'CSP 认证仅计最高分',
    icpc_ccpc_same_year_lower_score: '同年度 ICPC、CCPC 仅计最高分',
    competition_count_limit: '超出竞赛计入项目数上限',
    competition_top_three_limit: '超出竞赛计入项目数上限'
  })) assert.equal(scoreExclusionText(code), text)
  assert.equal(scoreExclusionText('按学院规定不予计入'), '按学院规定不予计入')
  assert.equal(scoreExclusionText(null), null)
})

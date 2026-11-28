import type { ViewState } from '@horsecoder/visual-core';

const size = { width: 166, height: 55 };
const palette = {
  read: '#306a85',
  audit: '#176b67',
  gate: '#714d98',
  repair: '#935620',
  output: '#3d617e',
};

const nodes = {
  recon: { title: '扫描原题材料', x: 85, y: 100, color: palette.read },
  solve: { title: '工程提取与求解', x: 295, y: 100, color: palette.read },
  entity: { title: '实体与来源审计', x: 505, y: 100, color: palette.audit },
  coverage: { title: '填土必查项覆盖审计', x: 715, y: 100, color: palette.audit },
  gate: { title: '证据完备性门禁', x: 925, y: 100, color: palette.gate },
  lookup: { title: '保存快照并定向补证', x: 925, y: 282, color: palette.repair },
  repair: { title: '修订目标结论', x: 715, y: 282, color: palette.repair },
  compare: { title: '修订保留性检查', x: 505, y: 282, color: palette.repair },
  recheck: { title: '复算并重新审计', x: 295, y: 282, color: palette.repair },
  hold: { title: 'Item 054 保持开放', x: 925, y: 474, color: palette.gate },
  exportWord: { title: '填写原 Word 模板', x: 715, y: 474, color: palette.output },
  readback: { title: '回读五条必留陈述', x: 505, y: 474, color: palette.output },
  result: { title: '交付待核验收记录', x: 295, y: 474, color: palette.output },
};

type NodeId = keyof typeof nodes;
type Point = { x: number; y: number };
type Side = 'left' | 'right' | 'top' | 'bottom';
const namespace = 'com.horsecoder.ple.fill';
const nodeId = (key: NodeId) => '@' + namespace + '/' + key;

function port(key: NodeId, side: Side): Point {
  const { x, y } = nodes[key];
  switch (side) {
    case 'left': return { x, y: y + size.height / 2 };
    case 'right': return { x: x + size.width, y: y + size.height / 2 };
    case 'top': return { x: x + size.width / 2, y };
    case 'bottom': return { x: x + size.width / 2, y: y + size.height };
  }
}

function link(
  source: NodeId, target: NodeId, from: Side, to: Side,
  name = '', color = '#547181', via: Point[] = [],
) {
  const id = '@' + namespace + '/' + source + '-' + target;
  const fromElementId = nodeId(source);
  const toElementId = nodeId(target);
  const points = [port(source, from), ...via, port(target, to)];
  return {
    id, name, color, type: 'fill-relation', points, fromElementId, toElementId,
    pendant: {
      data: {
        type: 'relation',
        detail: {
          id, thirdParty: false,
          relation: {
            id, relationName: source + '-' + target, relationTitle: name,
            relationType: 'ONE2ONE', modelMainId: fromElementId, modelRelatedId: toElementId,
            modelMainKey: [], modelRelatedKey: [],
          },
          link: { id, relationId: id, color, points },
        },
      },
    },
  };
}

export const fillCompactionReview: ViewState = {
  id: 'fill-compaction-acceptance-coverage-review',
  elements: (Object.keys(nodes) as NodeId[]).map((key) => {
    const { title, x, y, color } = nodes[key];
    const id = nodeId(key);
    return {
      id, name: title, type: 'fill-node', color, x, y, select: false, locked: false,
      pendant: {
        data: {
          type: 'model',
          detail: {
            id, familyId: namespace, thirdParty: false, size, fields: [],
            model: { id, module: 'sys', name: key, modelTitle: title, pk: [], fields: [] },
            component: { id, modelId: id, isCollapse: false, x, y },
          },
        },
      },
    };
  }),
  links: [
    link('recon', 'solve', 'right', 'left'),
    link('solve', 'entity', 'right', 'left'),
    link('entity', 'coverage', 'right', 'left'),
    link('coverage', 'gate', 'right', 'left'),
    link('gate', 'lookup', 'bottom', 'top', '有依据的漏项', palette.repair),
    link('lookup', 'repair', 'left', 'right', '', palette.repair),
    link('repair', 'compare', 'left', 'right', '', palette.repair),
    link('compare', 'recheck', 'left', 'right', '', palette.repair),
    link('recheck', 'entity', 'top', 'bottom', '修订后复审', palette.repair, [
      { x: port('recheck', 'top').x, y: 218 }, { x: port('entity', 'bottom').x, y: 218 },
    ]),
    link('gate', 'hold', 'right', 'right', '缺同料源试验', palette.gate, [
      { x: 1140, y: port('gate', 'right').y }, { x: 1140, y: port('hold', 'right').y },
    ]),
    link('hold', 'exportWord', 'left', 'right'),
    link('exportWord', 'readback', 'left', 'right'),
    link('readback', 'result', 'left', 'right'),
  ],
};

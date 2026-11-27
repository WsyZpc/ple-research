const familyId = 'com.horsecoder.agent';
const extractionName = 'lesMeshParameterExtractor';
const skillName = 'lesFireMeshRecalculation';
const extractionId = `@${familyId}/${extractionName}`;
const skillId = `@${familyId}/${skillName}`;
const relationName = 'lesMeshParametersToRecalculation';
const relationId = `@${familyId}/${relationName}`;

const extractionTitle = '提取 LES 网格定义与细化参数';
const skillTitle = '调用火源区网格重算与校验 Skill';
const linkColor = '#ffa940';
const extractionX = 100;
const skillX = 825;
const rowY = 175;
const size = { width: 350, height: 75 };

const exampleParameters = {
  bg_dx: 0.5,
  refine_level: 2,
  d_star: 3.74,
};

const parameterFields = [
  { name: 'bg_dx', type: 'Double', fieldTitle: '背景网格边长 (m)', notes: '背景网格单元边长，单位 m', notnull: true },
  { name: 'refine_level', type: 'Integer', fieldTitle: '细化层级', notes: '火源区相对背景网格的细化层级', notnull: true },
  { name: 'd_star', type: 'Double', fieldTitle: '特征火灾直径 (m)', notes: '特征火灾直径 D*，单位 m', notnull: true },
];
const parameterNames = parameterFields.map((field) => field.name);
const fieldDetails = parameterFields.map((field) => ({ field }));
const parameterLabel = Object.entries(exampleParameters)
  .map(([name, value]) => `${name}=${value}`)
  .join(' · ');

// 画布展示数据。exampleOutput 和 skill.exampleInput 用于对照上下游参数。
export const les_mesh_resolution_test = {
  id: 'les-mesh-resolution-demo',
  elements: [
    {
      id: extractionId,
      name: extractionTitle,
      type: 'model',
      color: '#5cdbd3',
      x: extractionX,
      y: rowY,
      select: false,
      locked: false,
      pendant: {
        data: {
          type: 'model',
          detail: {
            id: extractionId,
            model: {
              module: 'sys', modelTitle: extractionTitle, name: extractionName,
              id: extractionId, pk: [], fields: parameterFields,
            },
            component: { id: extractionId, modelId: extractionId, isCollapse: false, x: extractionX, y: rowY },
            fields: fieldDetails,
            nodeRole: 'LLM / 文本解析',
            exampleOutput: exampleParameters,
            familyId,
            thirdParty: false,
            size,
          },
        },
      },
    },
    {
      id: skillId,
      name: skillTitle,
      type: 'model',
      color: '#95de64',
      x: skillX,
      y: rowY,
      select: false,
      locked: false,
      pendant: {
        data: {
          type: 'model',
          detail: {
            id: skillId,
            model: {
              module: 'sys', modelTitle: skillTitle, name: skillName,
              id: skillId, pk: [], fields: parameterFields,
            },
            component: { id: skillId, modelId: skillId, isCollapse: false, x: skillX, y: rowY },
            fields: fieldDetails,
            nodeRole: '后端 Python Skill',
            skill: { name: skillName, exampleInput: exampleParameters },
            familyId,
            thirdParty: false,
            size,
          },
        },
      },
    },
  ],
  links: [
    {
      id: relationId,
      name: parameterLabel,
      color: linkColor,
      type: 'relation',
      points: [
        { x: extractionX + size.width, y: rowY + size.height / 2 },
        { x: skillX, y: rowY + size.height / 2 },
      ],
      fromElementId: extractionId,
      toElementId: skillId,
      pendant: {
        data: {
          type: 'relation',
          detail: {
            id: relationId,
            relation: {
              relationType: 'ONE2ONE',
              modelMainKey: parameterNames,
              relationName,
              modelMainId: extractionId,
              modelRelatedKey: parameterNames,
              modelRelatedId: skillId,
              relationTitle: '向火源区网格校验节点传递结构化 JSON 参数',
              id: relationId,
            },
            link: { id: relationId, relationId, color: linkColor, points: [] },
            thirdParty: false,
          },
        },
      },
    },
  ],
};

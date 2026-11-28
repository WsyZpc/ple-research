import React, { useEffect, useMemo, useRef, useState } from 'react';
import styles from './index.module.css';
import type { LoginProps } from './types';

import VisualDiagram from '@horsecoder/visual-core';
import { Button, Modal } from 'antd';
import { flowRunFacade } from '@/src/flows/com.horsecoder.common.whuTalent.flowTesting.core/Run';

import type {
  ElementState,
  LinkState,
  VisualCanvasConfig,
  VisualElementConfig,
  VisualLinkConfig,
  VisualToolbarConfig,
} from '@horsecoder/visual-core';
import StandardModelEntityWrapper from '@/components/StandardModelEntity/wrapper';
import StandardModelLinkWrapper from '@/components/StandardModelLink/wrapper';
import type { Point } from '@/utils/design/Point';
import { getView, refreshCanvasLocked, setView } from './handler/handler/diagramHandler';

import { les_mesh_resolution_test } from './test/les_mesh_resolution_test';
import { fillCompactionReview } from './test/fill_compaction_review';

function FillReviewNode({ element }: { element: { state: ElementState } }) {
  return (
    <div className={styles.fillNode} style={{ backgroundColor: element.state.color }}>
      {element.state.name}
    </div>
  );
}

function FillReviewLink({ link }: { link: { state: LinkState; slotFrom?: Point } }) {
  const { color = '#547181', name, pendant } = link.state;
  const route = pendant?.data.detail.link.points as Point[] | undefined;
  const first = link.state.points[0];
  // The canvas projects its generated slot into the visible SVG using the current view offset.
  const offsetX = first && link.slotFrom ? first.x - link.slotFrom.x : 0;
  const offsetY = first && link.slotFrom ? first.y - link.slotFrom.y : 0;
  const points: Point[] = route?.map(({ x, y }) => ({ x: x + offsetX, y: y + offsetY })) ?? link.state.points;
  if (points.length < 2) return null;

  const end = points[points.length - 1];
  const previous = points[points.length - 2];
  const dx = end.x - previous.x;
  const dy = end.y - previous.y;
  const length = Math.hypot(dx, dy);
  if (!length) return null;
  const baseX = end.x - 9 * dx / length;
  const baseY = end.y - 9 * dy / length;
  const sideX = 4 * dy / length;
  const sideY = 4 * dx / length;
  const line = points.map(({ x, y }) => x + ',' + y).join(' ');
  const arrow = [end, { x: baseX + sideX, y: baseY - sideY }, { x: baseX - sideX, y: baseY + sideY }]
    .map(({ x, y }) => x + ',' + y).join(' ');

  let labelSegment = 1;
  for (let i = 2; i < points.length; i++) {
    const distance = Math.hypot(points[i].x - points[i - 1].x, points[i].y - points[i - 1].y);
    const best = Math.hypot(
      points[labelSegment].x - points[labelSegment - 1].x,
      points[labelSegment].y - points[labelSegment - 1].y,
    );
    if (distance > best) labelSegment = i;
  }
  const [from, to] = [points[labelSegment - 1], points[labelSegment]];
  const vertical = from.x === to.x;

  return (
    <g>
      <polyline points={line} fill="none" stroke={color} strokeWidth={2.5} strokeLinejoin="round" />
      <polygon points={arrow} fill={color} />
      {name && (
        <text
          x={(from.x + to.x) / 2 + (vertical ? 12 : 0)}
          y={(from.y + to.y) / 2 - (vertical ? 4 : 9)}
          textAnchor={vertical ? 'start' : 'middle'}
          className={styles.fillLinkLabel}
          fill={color}
        >
          {name}
        </text>
      )}
    </g>
  );
}

/**
 * 组件布局: 登录
 */
const LoginPage: React.FC<LoginProps> = () => {
  const [runError, setRunError] = useState('');
  const [running, setRunning] = useState(false);
  const [workflow, setWorkflow] = useState<'les' | 'fill'>('les');
  const fillSelected = workflow === 'fill';

  // 内部数据: diagramRefInner(diagramRef)
  const diagramRef = useRef<React.ComponentRef<typeof VisualDiagram>>(null);
  // 内部数据: 工具栏配置(toolbarConfig)
  const toolbarConfig: VisualToolbarConfig = useMemo(() => [], []);

  useEffect(() => {
    if (diagramRef.current) {
      refreshCanvasLocked(diagramRef, fillSelected);
      setView(diagramRef, fillSelected ? fillCompactionReview : les_mesh_resolution_test);
    }
  }, [fillSelected]);

  const elementConfig: VisualElementConfig = useMemo(
    () => ({
      components: {
        'fill-node': { component: FillReviewNode, minSize: { width: 166, height: 55 } },
        model: {
          component: StandardModelEntityWrapper,
          minSize: {
            width: 100,
            height: 55,
          },
        },
      },
    }),
    [],
  );

  const linkConfig: VisualLinkConfig = useMemo(
    () => ({
      components: {
        'fill-relation': { component: FillReviewLink, hasArrow: true, showName: true },
        relation: {
          component: StandardModelLinkWrapper,
          hasArrow: true,
          showName: true,
        },
      },
    }),
    [],
  );

  const canvasConfig: VisualCanvasConfig = useMemo(
    () => ({
      toolbarConfig,
      elementConfig,
      linkConfig,
      globalConfig: {
        gridSize: 25,
      },
    }),
    [toolbarConfig, elementConfig, linkConfig],
  );


  return (
    <>
      <div
        className={styles.div}
      >
        <div className={styles.workflowSelector} role="group" aria-label="选择编排">
          <Button type={fillSelected ? 'default' : 'primary'} aria-pressed={!fillSelected}
            disabled={running} onClick={() => { setWorkflow('les'); setRunError(''); }}>
            LES 网格分辨率
          </Button>
          <Button type={fillSelected ? 'primary' : 'default'} aria-pressed={fillSelected}
            disabled={running} onClick={() => { setWorkflow('fill'); setRunError(''); }}>
            填土压实验收
          </Button>
        </div>
        {fillSelected && (
          <span className={styles.workflowSummary}>
            回放路径预览 · 局部修订 1 次 · 覆盖 10/10 · 本地评分 78/108
          </span>
        )}
        {runError && <span role="alert">{runError}</span>}
        {!fillSelected && <Button
          className={styles.divButton0}
          type="primary"
          loading={running}
          onClick={async () => {
            setRunError('');
            setRunning(true);
            try {
              const diagram = getView(diagramRef);
              if (!diagram) {
                throw new Error('画布还没初始化，请稍后再运行。');
              }

              const { result } = await flowRunFacade({
                structure: JSON.stringify({
                  ...diagram,
                  blackboard: {
                    task_dir: 'demo',
                    instruction: '扫描任务资料',
                    retry_count: 0,
                  },
                }),
              });

              if (typeof result !== 'string') {
                throw new Error('后端没有返回运行结果。');
              }
              const board = JSON.parse(result) as {
                file_index?: unknown[];
                authority_docs?: string[];
              } | null;
              if (!Array.isArray(board?.file_index) || !Array.isArray(board?.authority_docs)) {
                throw new Error('后端没有返回文件索引，请检查黑板和后端版本。');
              }

              Modal.info({
                title: '工作区扫描结果',
                content: (
                  <pre style={{ maxHeight: 320, overflow: 'auto', whiteSpace: 'pre-wrap' }}>
                    {JSON.stringify({
                      file_index: board.file_index,
                      authority_docs: board.authority_docs,
                    }, null, 2)}
                  </pre>
                ),
              });
            } catch (error) {
              setRunError(error instanceof Error ? error.message : '运行失败，请检查接口响应。');
            } finally {
              setRunning(false);
            }
          }}
        >
          {`运行`}
        </Button>}
      </div>
      <VisualDiagram
        // className={styles.divDiv0}
        ref={diagramRef}
        // {...props.actions.eventsDiv}
        canvasConfig={canvasConfig}
      />
    </>
  );
};

export default LoginPage;

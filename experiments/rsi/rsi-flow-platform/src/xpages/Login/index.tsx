import React, { useEffect, useMemo, useRef, useState } from 'react';
import styles from './index.module.css';
import type { LoginProps } from './types';

import VisualDiagram from '@horsecoder/visual-core';
import { Button, Modal } from 'antd';
import { flowRunFacade } from '@/src/flows/com.horsecoder.common.whuTalent.flowTesting.core/Run';

import type {
  VisualCanvasConfig,
  VisualElementConfig,
  VisualLinkConfig,
  VisualToolbarConfig,
} from '@horsecoder/visual-core';
import StandardModelEntityWrapper from '@/components/StandardModelEntity/wrapper';
import StandardModelLinkWrapper from '@/components/StandardModelLink/wrapper';
import { getView, refreshCanvasLocked, setView } from './handler/handler/diagramHandler';

import { les_mesh_resolution_test } from './test/les_mesh_resolution_test';


/**
 * 组件布局: 登录
 */
const LoginPage: React.FC<LoginProps> = () => {
  const [runError, setRunError] = useState('');
  const [running, setRunning] = useState(false);

  // 内部数据: diagramRefInner(diagramRef)
  const diagramRef = useRef<React.ComponentRef<typeof VisualDiagram>>(null);
  // 内部数据: 工具栏配置(toolbarConfig)
  const toolbarConfig: VisualToolbarConfig = useMemo(() => [], []);

  useEffect(() => {
    if (diagramRef.current) {
      refreshCanvasLocked(diagramRef, false);
      setView(diagramRef, les_mesh_resolution_test);
    }
  }, []);

  const elementConfig: VisualElementConfig = useMemo(
    () => ({
      components: {
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
        {runError && <span role="alert">{runError}</span>}
        <Button
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
        </Button>
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

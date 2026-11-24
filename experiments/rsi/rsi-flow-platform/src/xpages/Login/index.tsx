import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Button } from 'antd';
import styles from './index.module.css';
import type { LoginProps } from './types';

import VisualDiagram, { VisualToolbarConfig } from '@horsecoder/visual-core';


import {
  VisualCanvasConfig,
  VisualElementConfig,
  VisualLinkConfig,
} from '@horsecoder/visual-core';
import StandardModelEntityWrapper from '@/components/StandardModelEntity/wrapper';
import StandardModelLinkWrapper from '@/components/StandardModelLink/wrapper';
import { getView, refreshCanvasLocked, refreshElementLocked, setView } from './handler/handler/diagramHandler';

import { first_test } from './test/first_test';
import { user_favorites_test } from './test/user_favorites_test';
import { flowRun } from '@/src/flows/com.horsecoder.common.whuTalent.flowTesting.core/Run';
import { user_excel_test } from './test/user_excel_test';


/**
 * 组件布局: 登录
 */
const LoginPage: React.FC<LoginProps> = () => {



  const [runError, setRunError] = useState('');
  const [running, setRunning] = useState(false);

  // 内部数据: diagramRefInner(diagramRef)
  const diagramRef = useRef<any>(null);
  // 内部数据: 工具栏配置(toolbarConfig)
  const toolbarConfig: VisualToolbarConfig = useMemo(() => [], []);

  useEffect(() => {
    if (diagramRef.current) {
      refreshCanvasLocked(diagramRef, false);
      setView(diagramRef, user_excel_test);
    };
  }, [])




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
              await flowRun({ structure: JSON.stringify(getView(diagramRef)) });
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

import { LogoutOutlined, UserOutlined } from '@ant-design/icons';
import { Button, ConfigProvider, Space, Tag, message } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import type { ReactNode } from 'react';

import { history } from '@umijs/max';

// 局部类型，匹配实际路由结构
type MenuDataItem = {
  path?: string;
  name?: string;
  icon?: React.ReactNode;
  children?: MenuDataItem[];
  routes?: MenuDataItem[];
  hideInMenu?: boolean;
  hideChildrenInMenu?: boolean;
  disabledTooltip?: boolean;
  tooltip?: string;
};

import './global.less';
import {
  clearAuthState,
  getCurrentUser,
  getEdition,
  getHealth,
  logoutAuth,
} from '@/services/api';
import type { AuthUser, EditionCapabilityPayload } from '@/types/api';
import { displayEditionName } from '@/utils/display';

type InitialState = {
  name: string;
  authEnabled: boolean;
  currentUser?: AuthUser | null;
  edition?: EditionCapabilityPayload | null;
};

type LayoutRuntimeContext = {
  initialState?: InitialState;
  setInitialState?: (
    updater: (current: InitialState | undefined) => InitialState,
  ) => Promise<void> | void;
};

function applyMenuTooltipPolicy(items: MenuDataItem[] = []): MenuDataItem[] {
  return items.map((item) => ({
    ...item,
    disabledTooltip: true,
    children: item.children ? applyMenuTooltipPolicy(item.children) : item.children,
    routes: item.routes ? applyMenuTooltipPolicy(item.routes) : item.routes,
  })) as MenuDataItem[];
}

const DEFAULT_APP_NAME = 'AI漫剧创作者控制台';
const DEFAULT_INITIAL_STATE: InitialState = {
  name: DEFAULT_APP_NAME,
  authEnabled: false,
  currentUser: null,
  edition: null,
};

const LOGIN_PATHS = new Set(['/login']);

export function rootContainer(container: ReactNode) {
  return (
    <ConfigProvider
      locale={zhCN}
      theme={{
        token: {
          colorPrimary: '#0050b3',
          colorBorder: '#8c8c8c',
        },
      }}
    >
      {container}
    </ConfigProvider>
  );
}

export async function getInitialState(): Promise<InitialState> {
  try {
    const [health, session, edition] = await Promise.all([
      getHealth(),
      getCurrentUser(),
      getEdition(),
    ]);
    return {
      name: DEFAULT_APP_NAME,
      authEnabled: health.auth_enabled,
      currentUser: session.user ?? null,
      edition,
    };
  } catch {
    return DEFAULT_INITIAL_STATE;
  }
}

function currentPathname() {
  return history.location.pathname;
}

function navigateTo(path: string) {
  if (history.location.pathname !== path) {
    history.push(path);
  }
}

export const layout = ({ initialState, setInitialState }: LayoutRuntimeContext) => {
  const pathname = currentPathname();

  return {
    title: DEFAULT_APP_NAME,
    logo: false,
    menu: {
      locale: false,
    },
    menuDataRender: (menuData: MenuDataItem[]) => applyMenuTooltipPolicy(menuData),
    layout: 'mix',
    onPageChange: () => {
      const activePathname = currentPathname();
      const authEnabled = Boolean(initialState?.authEnabled);
      const hasUser = Boolean(initialState?.currentUser);

      if (authEnabled && !hasUser && !LOGIN_PATHS.has(activePathname)) {
        navigateTo('/login');
        return;
      }

      if (hasUser && activePathname === '/login') {
        navigateTo('/dashboard');
      }
    },
    rightContentRender: () => {
      if (!initialState?.currentUser) {
        return (
          <Space>
            {authEnabledTag(initialState?.authEnabled ?? false)}
            {editionTag(initialState?.edition)}
          </Space>
        );
      }

      return (
        <Space>
          {authEnabledTag(initialState?.authEnabled ?? false)}
          {editionTag(initialState?.edition)}
          <Tag icon={<UserOutlined />} color="blue">
            {initialState.currentUser.display_name}
          </Tag>
          <Button
            icon={<LogoutOutlined />}
            onClick={async () => {
              try {
                await logoutAuth();
              } catch {
                message.warning('退出登录接口返回异常，已清理本地登录态');
              } finally {
                clearAuthState();
                await setInitialState?.((current) => ({
                  ...(current ?? DEFAULT_INITIAL_STATE),
                  currentUser: null,
                }));
                navigateTo('/login');
              }
            }}
          >
            退出
          </Button>
        </Space>
      );
    },
    pageTitleRender: false,
    menuHeaderRender: undefined,
    disableContentMargin: pathname === '/login',
  };
};

function authEnabledTag(authEnabled: boolean) {
  return (
    <Tag color={authEnabled ? 'green' : 'default'}>
      {authEnabled ? '账号已连接' : '登录关闭'}
    </Tag>
  );
}

function editionTag(edition?: EditionCapabilityPayload | null) {
  return <Tag color="purple">{displayEditionName(edition?.display_name ?? '创作者个人版')}</Tag>;
}

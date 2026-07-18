import { Alert, Button, Card, Col, Descriptions, Form, Input, List, Row, Space, Tag, Typography, message } from 'antd';
import { useEffect, useState } from 'react';
import { EyeInvisibleOutlined, EyeOutlined } from '@ant-design/icons';

import { history } from '@umijs/max';

import {
  getAuthConfig,
  getCurrentUser,
  passwordLogin,
  persistAuthState,
} from '@/services/api';
import type { AuthConfigPayload } from '@/types/api';

const { Paragraph, Text, Title } = Typography;

function navigateTo(path: string) {
  if (history.location.pathname !== path) {
    history.push(path);
  }
}

export default function LoginPage() {
  const [messageApi, contextHolder] = message.useMessage();
  const [submitting, setSubmitting] = useState(false);
  const [authConfig, setAuthConfig] = useState<AuthConfigPayload>();

  useEffect(() => {
    document.title = '登录 - AI漫剧创作者控制台';
    void Promise.all([getAuthConfig(), getCurrentUser()])
      .then(([config, session]) => {
        setAuthConfig(config);
        if (session.authenticated && session.user) {
          persistAuthState(session);
          navigateTo('/dashboard');
        }
      })
      .catch(() => undefined);
  }, []);

  const authDisabled = authConfig ? !authConfig.auth_enabled : false;
  const passwordLoginDisabled = authConfig ? !authConfig.password_login_enabled : false;
  const loginAlertType = passwordLoginDisabled ? 'warning' : authDisabled ? 'info' : 'success';
  const loginAlertMessage = passwordLoginDisabled
    ? '当前环境未开放账号登录'
    : authDisabled
      ? '当前环境未强制鉴权'
      : '当前环境可直接进入';
  const loginAlertDescription = passwordLoginDisabled
    ? authConfig?.auth_reason ?? '先确认本地鉴权配置，再进入工作台。'
    : authDisabled
      ? '登录主要用于保留个人会话和工作台状态。'
      : '登录后会直接进入总控板，继续项目推进与样片审核。';

  const runtimeFacts = [
    ['版本', authConfig?.edition_display_name ?? '创作者个人创作者版'],
    ['模式', '单人工作台'],
    ['鉴权', authDisabled ? '可匿名访问' : '密码登录'],
    ['进入后默认页', '总控板 /dashboard'],
  ];

  const workspaceHighlights = [
    '先确认环境与账号，再进入总控板。',
    '总控板先看系统状态，再决定去哪个项目。',
    '项目页只负责挑当前最值得推进的项目。',
    'Creator 页负责执行、审核和放行。',
  ];

  return (
    <>
      {contextHolder}
      <div className="aicomic-login-page">
        <div className="aicomic-login-shell">
          <div className="aicomic-login-header">
            <div>
              <Title level={1} className="aicomic-login-title">
                进入创作者控制台
              </Title>
              <Paragraph type="secondary" style={{ marginBottom: 6 }}>
                先确认当前环境与账号，再进入工作台主链。
              </Paragraph>
            </div>
            <Space wrap className="aicomic-login-meta">
              <Tag color="blue">创作者版</Tag>
              <Tag color="green">单人模式</Tag>
              <Tag color="geekblue">密码登录</Tag>
            </Space>
          </div>

          <Row gutter={[16, 16]} align="stretch">
            <Col xs={24} xl={13}>
              <div className="aicomic-login-column">
                <Alert
                  type={loginAlertType}
                  showIcon
                  message={loginAlertMessage}
                  description={loginAlertDescription}
                />

                <Card title="进入前确认" size="small" className="aicomic-login-card">
                  <Space direction="vertical" size={10} style={{ width: '100%' }}>
                    <Descriptions size="small" column={2} colon={false}>
                      {runtimeFacts.map(([label, value]) => (
                        <Descriptions.Item key={label} label={label}>
                          <Text>{value}</Text>
                        </Descriptions.Item>
                      ))}
                    </Descriptions>
                    <List
                      size="small"
                      split={false}
                      dataSource={workspaceHighlights}
                      renderItem={(item) => <List.Item style={{ paddingBlock: 2 }}>{item}</List.Item>}
                    />
                  </Space>
                </Card>
              </div>
            </Col>

            <Col xs={24} xl={11}>
              <Card title="账号登录" size="small" className="aicomic-login-card">
                <Form
                  layout="vertical"
                  requiredMark={false}
                  onFinish={async (values) => {
                    setSubmitting(true);
                    try {
                      const session = await passwordLogin({
                        username: String(values.username ?? '').trim(),
                        password: String(values.password ?? ''),
                      });
                      persistAuthState(session);
                      messageApi.success('登录成功');
                      navigateTo('/dashboard');
                    } catch (error) {
                      console.error(error);
                      messageApi.error('用户名或密码错误');
                    } finally {
                      setSubmitting(false);
                    }
                  }}
                >
                  <Form.Item
                    name="username"
                    label="账号"
                    rules={[{ required: true, message: '请输入用户名' }]}
                  >
                    <Input size="middle" placeholder="个人账号" autoComplete="username" />
                  </Form.Item>
                  <Form.Item
                    name="password"
                    label="密码"
                    rules={[{ required: true, message: '请输入密码' }]}
                  >
                    <Input.Password
                      size="middle"
                      placeholder="密码"
                      autoComplete="current-password"
                      iconRender={(visible) => (
                        <button
                          type="button"
                          aria-label={visible ? '隐藏密码' : '显示密码'}
                          aria-pressed={visible}
                          style={{ border: 'none', background: 'none', cursor: 'pointer', padding: 0 }}
                          onMouseDown={(e) => e.preventDefault()}
                        >
                          {visible ? <EyeOutlined /> : <EyeInvisibleOutlined />}
                        </button>
                      )}
                    />
                  </Form.Item>
                  <Button
                    type="primary"
                    htmlType="submit"
                    block
                    size="middle"
                    loading={submitting}
                    disabled={passwordLoginDisabled}
                  >
                    登录
                  </Button>
                </Form>
              </Card>
            </Col>
          </Row>
        </div>
      </div>
    </>
  );
}

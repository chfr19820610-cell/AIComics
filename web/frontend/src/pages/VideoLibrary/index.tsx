import { ReloadOutlined, PlayCircleOutlined, FileOutlined, DownloadOutlined } from '@ant-design/icons';
import { PageContainer, ProCard } from '@ant-design/pro-components';
import {
  Button,
  Card,
  Col,
  Empty,
  List,
  message,
  Row,
  Skeleton,
  Space,
  Tag,
  Typography,
} from 'antd';
import { useCallback, useEffect, useRef, useState } from 'react';
import { buildVideoStreamUrl, getVideos } from '@/services/api';
import type { VideoRecord } from '@/types/api';

const { Text, Title } = Typography;

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatTime(unixSeconds: number): string {
  const d = new Date(unixSeconds * 1000);
  return d.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

function extractLabel(filename: string): string {
  // Try to produce a human-readable label from mp4 filenames
  // E01_cinematic-liquid-glass_20260719_182619.mp4 → "E01 · Cinematic Liquid Glass"
  const withoutExt = filename.replace(/\.mp4$/i, '');
  const parts = withoutExt.split('_');
  if (parts.length >= 2) {
    // First part = episode code, second = style name, rest = timestamp
    const episode = parts[0];
    const style = parts[1]
      ? parts[1]
        .split('-')
        .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
        .join(' ')
      : '';
    return style ? `${episode} · ${style}` : episode;
  }
  return withoutExt;
}

export default function VideoLibraryPage() {
  const [videos, setVideos] = useState<VideoRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedVideo, setSelectedVideo] = useState<VideoRecord | null>(null);
  const [error, setError] = useState<string | null>(null);
  const mountedRef = useRef(true);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const payload = await getVideos();
      if (mountedRef.current) {
        setVideos(payload.items ?? []);
        // Auto-select first video if nothing selected
        setSelectedVideo((prev) => {
          if (!prev && payload.items?.length > 0) return payload.items[0];
          return prev;
        });
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : '加载视频列表失败';
      if (mountedRef.current) {
        setError(msg);
        message.error(msg);
      }
    } finally {
      if (mountedRef.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    void loadData();
    return () => { mountedRef.current = false; };
  }, [loadData]);

  return (
    <PageContainer
      title="视频库"
      subTitle="浏览和预览已生成的视频文件"
      extra={[
        <Button
          key="refresh"
          size="small"
          icon={<ReloadOutlined />}
          onClick={() => void loadData()}
        >
          刷新
        </Button>,
      ]}
    >
      {loading ? (
        <Skeleton active paragraph={{ rows: 6 }} />
      ) : error && videos.length === 0 ? (
        <Card>
          <Empty
            description={
              <Space direction="vertical">
                <Text type="danger">{error}</Text>
                <Button onClick={() => void loadData()}>重试</Button>
              </Space>
            }
          />
        </Card>
      ) : videos.length === 0 ? (
        <Card>
          <Empty description="暂无视频文件，请先生成视频后再来查看" />
        </Card>
      ) : (
        <Row gutter={[16, 16]}>
          {/* Video player area */}
          <Col xs={24} lg={16}>
            <ProCard
              title={
                selectedVideo
                  ? extractLabel(selectedVideo.filename)
                  : '预览'
              }
              bordered
              className="aicomic-compact-card"
              style={{ minHeight: 400 }}
            >
              {selectedVideo ? (
                <video
                  key={selectedVideo.filename}
                  controls
                  style={{ width: '100%', maxHeight: '70vh', borderRadius: 4 }}
                  preload="metadata"
                >
                  <source
                    src={buildVideoStreamUrl(selectedVideo.filename)}
                    type="video/mp4"
                  />
                  您的浏览器不支持视频播放
                </video>
              ) : (
                <Empty description="请在左侧选择一个视频" />
              )}
            </ProCard>
          </Col>

          {/* Video list sidebar */}
          <Col xs={24} lg={8}>
            <ProCard
              title={
                <Space>
                  <FileOutlined />
                  <span>文件列表 ({videos.length})</span>
                </Space>
              }
              bordered
              className="aicomic-compact-card"
              style={{ maxHeight: '75vh', overflow: 'auto' }}
            >
              <List
                size="small"
                dataSource={videos}
                locale={{ emptyText: '暂无视频文件' }}
                renderItem={(item) => {
                  const isActive = selectedVideo?.filename === item.filename;
                  const label = extractLabel(item.filename);
                  const isLatest = item.filename.startsWith('E') && item.filename.includes('_latest_');
                  const isRealMp4 = item.filename.endsWith('.mp4') && !isLatest;

                  // Skip symlink _latest_ entries for cleaner display (they duplicate real files)
                  if (item.is_symlink && isLatest) return null;

                  return (
                    <List.Item
                      key={item.filename}
                      onClick={() => setSelectedVideo(item)}
                      style={{
                        cursor: 'pointer',
                        background: isActive ? '#e6f4ff' : undefined,
                        padding: '8px 12px',
                        borderRadius: 4,
                        marginBottom: 4,
                      }}
                    >
                      <List.Item.Meta
                        avatar={<PlayCircleOutlined style={{ fontSize: 20, color: isActive ? '#1677ff' : '#8c8c8c' }} />}
                        title={
                          <Space size={4}>
                            <Text strong={isActive} style={{ fontSize: 13 }}>
                              {label || item.filename}
                            </Text>
                            {item.is_symlink && <Tag color="green" style={{ fontSize: 10, lineHeight: '16px' }}>最新</Tag>}
                          </Space>
                        }
                        description={
                          <Space size={12}>
                            <Text type="secondary" style={{ fontSize: 12 }}>
                              {formatSize(item.size_bytes)}
                            </Text>
                            <Text type="secondary" style={{ fontSize: 12 }}>
                              {formatTime(item.mtime)}
                            </Text>
                          </Space>
                        }
                      />
                    </List.Item>
                  );
                }}
              />
            </ProCard>
          </Col>
        </Row>
      )}
    </PageContainer>
  );
}

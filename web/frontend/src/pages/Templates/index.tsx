import React, { useEffect, useState } from 'react';
import { Card, Table, Tag, Input, Select, Button, Modal, Spin, message } from 'antd';
import { browseTemplates, previewTemplate } from '@/services/api';
import type { TemplateSummary, TemplatePreview } from '@/services/api';

const { Search } = Input;
const { Option } = Select;

export default function TemplatesPage() {
  const [templates, setTemplates] = useState<TemplateSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [genreFilter, setGenreFilter] = useState<string | undefined>(undefined);
  const [previewData, setPreviewData] = useState<TemplatePreview | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);

  async function loadTemplates(genre?: string) {
    setLoading(true);
    try {
      const result = await browseTemplates(genre);
      setTemplates(result.templates);
    } catch (e) {
      message.error('加载模板失败');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadTemplates();
  }, []);

  async function handlePreview(templateId: string) {
    setModalOpen(true);
    setPreviewLoading(true);
    try {
      const data = await previewTemplate(templateId);
      setPreviewData(data);
    } catch (e) {
      message.error('预览失败');
    } finally {
      setPreviewLoading(false);
    }
  }

  const columns = [
    { title: 'ID', dataIndex: 'id', key: 'id' },
    { title: '题材', dataIndex: 'genre', key: 'genre', render: (g: string) => <Tag color="blue">{g}</Tag> },
    { title: '幕数', dataIndex: 'acts_count', key: 'acts_count' },
    { title: '场景', dataIndex: 'locations_count', key: 'locations_count' },
    { title: '角色', dataIndex: 'characters_count', key: 'characters_count' },
    { title: '默认钩子', dataIndex: 'default_hook', key: 'default_hook', ellipsis: true },
    {
      title: '操作', key: 'action',
      render: (_: unknown, record: TemplateSummary) => (
        <Button size="small" onClick={() => handlePreview(record.id)}>预览</Button>
      ),
    },
  ];

  return (
    <div>
      <Card title="漫剧模板库" extra={
        <Select
          allowClear
          placeholder="按题材筛选"
          style={{ width: 200 }}
          value={genreFilter}
          onChange={(v) => { setGenreFilter(v); loadTemplates(v); }}
        >
          <Option value="恐怖">恐怖</Option>
          <Option value="职场">职场</Option>
          <Option value="修仙">修仙</Option>
          <Option value="悬疑">悬疑</Option>
          <Option value="甜宠">甜宠</Option>
          <Option value="言情">言情</Option>
        </Select>
      }>
        <Table
          dataSource={templates}
          columns={columns}
          rowKey="id"
          loading={loading}
          pagination={{ pageSize: 10 }}
        />
      </Card>

      <Modal
        title="模板预览"
        open={modalOpen}
        onCancel={() => { setModalOpen(false); setPreviewData(null); }}
        footer={null}
        width={800}
      >
        {previewLoading ? <Spin /> : previewData && (
          <div>
            <h3>{previewData.genre}</h3>
            <h4>幕结构</h4>
            {previewData.acts?.map(act => (
              <Card key={act.act_id} size="small" style={{ marginBottom: 8 }}>
                <strong>{act.title}</strong> — {act.beat}
              </Card>
            ))}
            <h4>角色</h4>
            {previewData.characters?.map(c => (
              <Tag key={c.name}>{c.name} ({c.role})</Tag>
            ))}
            <h4>场景</h4>
            {previewData.locations?.map(loc => <Tag key={loc}>{loc}</Tag>)}
          </div>
        )}
      </Modal>
    </div>
  );
}

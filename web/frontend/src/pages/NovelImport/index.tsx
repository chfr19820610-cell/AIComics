import React, { useState } from 'react';
import { Card, Input, Select, InputNumber, Button, Alert, Spin, message } from 'antd';
import { importNovel } from '@/services/api';

const { TextArea } = Input;
const { Option } = Select;

export default function NovelImportPage() {
  const [text, setText] = useState('');
  const [template, setTemplate] = useState('horror');
  const [episodes, setEpisodes] = useState(12);
  const [shotsPerEp, setShotsPerEp] = useState(10);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<Record<string, unknown> | null>(null);

  async function handleImport() {
    if (!text.trim()) {
      message.warning('请输入小说文本');
      return;
    }
    setLoading(true);
    try {
      const r = await importNovel({
        text,
        template,
        episodes,
        shots_per_episode: shotsPerEp,
      });
      setResult(r);
      message.success('导入成功');
    } catch (e) {
      message.error('导入失败');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <Card title="小说导入 → 漫剧蓝图">
        <Alert
          type="info"
          message="粘贴小说文本，选择模板，系统自动拆分章节、生成蓝图、规划分镜"
          style={{ marginBottom: 16 }}
        />

        <div style={{ marginBottom: 16 }}>
          <label style={{ marginRight: 8 }}>模板:</label>
          <Select value={template} onChange={setTemplate} style={{ width: 200 }}>
            <Option value="horror">恐怖</Option>
            <Option value="workplace">职场</Option>
            <Option value="cultivation">修仙</Option>
            <Option value="mystery">悬疑</Option>
            <Option value="sweetpet">甜宠</Option>
            <Option value="romance">言情</Option>
          </Select>

          <label style={{ marginLeft: 16, marginRight: 8 }}>集数:</label>
          <InputNumber min={1} max={52} value={episodes} onChange={(v) => setEpisodes(v || 12)} />

          <label style={{ marginLeft: 16, marginRight: 8 }}>每集分镜:</label>
          <InputNumber min={1} max={30} value={shotsPerEp} onChange={(v) => setShotsPerEp(v || 10)} />
        </div>

        <TextArea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="粘贴小说文本..."
          rows={10}
          style={{ marginBottom: 16 }}
        />

        <Button type="primary" onClick={handleImport} loading={loading}>
          导入并生成蓝图
        </Button>

        {loading && <Spin style={{ marginLeft: 16 }} />}

        {result && (
          <Card title="导入结果" style={{ marginTop: 16 }}>
            <pre style={{ maxHeight: 300, overflow: 'auto', background: '#f5f5f5', padding: 12 }}>
              {JSON.stringify(result, null, 2)}
            </pre>
          </Card>
        )}
      </Card>
    </div>
  );
}

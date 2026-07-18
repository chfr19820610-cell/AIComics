import { Card, Statistic } from 'antd';

type MetricCardProps = {
  title: string;
  value: number | string;
  suffix?: string;
};

export default function MetricCard({ title, value, suffix }: MetricCardProps) {
  return (
    <Card size="small" className="aicomic-metric-card">
      <Statistic title={title} value={value} suffix={suffix} />
    </Card>
  );
}

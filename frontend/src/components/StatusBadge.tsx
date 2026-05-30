const COLORS: Record<string, string> = {
  success: 'bg-green-100 text-green-800',
  failed: 'bg-red-100 text-red-800',
  pending_confirmation: 'bg-yellow-100 text-yellow-800',
  rejected: 'bg-gray-100 text-gray-600',
  resolved: 'bg-gray-100 text-gray-600',
  warning: 'bg-yellow-100 text-yellow-800',
  critical: 'bg-red-100 text-red-800',
  info: 'bg-blue-100 text-blue-800',
};

const LABELS: Record<string, string> = {
  success: '成功',
  failed: '失败',
  pending_confirmation: '待确认',
  rejected: '已拒绝',
  resolved: '已处理',
  warning: '警告',
  critical: '严重',
  info: '信息',
};

export function StatusBadge({ status }: { status: string }) {
  const color = COLORS[status] || 'bg-gray-100 text-gray-600';
  const label = LABELS[status] || status;
  return (
    <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${color}`}>
      {label}
    </span>
  );
}

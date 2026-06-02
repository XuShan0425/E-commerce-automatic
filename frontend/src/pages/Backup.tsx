import { useCallback, useEffect, useState } from 'react';
import { api } from '../api/client';
import { useApp } from '../contexts/AppContext';
import { StatusBadge } from '../components/StatusBadge';

interface BackupItem {
  filename: string;
  size_bytes: number;
  size_display: string;
  created_at: string | null;
}

interface BackupListResponse {
  backups: BackupItem[];
  total: number;
  backup_dir: string;
}

export function Backup() {
  const { addToast } = useApp();
  const [backups, setBackups] = useState<BackupItem[]>([]);
  const [backupDir, setBackupDir] = useState('');
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [restoring, setRestoring] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.get<BackupListResponse>('/backups/');
      setBackups(data.backups);
      setBackupDir(data.backup_dir);
    } catch (e: any) {
      addToast(e?.message || '无法获取备份列表', 'error');
    }
    setLoading(false);
  }, [addToast]);

  useEffect(() => { load(); }, [load]);

  async function handleTriggerBackup() {
    setRunning(true);
    try {
      const result = await api.post<{ success: boolean; filename?: string; error?: string; message?: string }>('/backups/trigger');
      if (result.success) {
        addToast(result.message || '备份成功', 'success');
        load();
      } else {
        addToast(result.error || '备份失败', 'error');
      }
    } catch (e: any) {
      addToast(e.message || '备份请求失败', 'error');
    }
    setRunning(false);
  }

  async function handleRestore(filename: string) {
    if (!confirm(`确认从备份 "${filename}" 恢复？\n\n警告: 恢复将覆盖当前数据库中的所有数据！此操作不可撤销。`)) return;

    setRestoring(filename);
    try {
      const result = await api.post<{ success: boolean; error?: string; message?: string }>('/backups/restore', { filename });
      if (result.success) {
        addToast(result.message || '恢复成功', 'success');
      } else {
        addToast(result.error || '恢复失败', 'error');
      }
    } catch (e: any) {
      addToast(e.message || '恢复请求失败', 'error');
    }
    setRestoring(null);
  }

  if (loading) {
    return <div className="text-center py-12 text-gray-400">加载中...</div>;
  }

  return (
    <div className="space-y-6 max-w-4xl">
      {/* ── 头部操作区 ── */}
      <section className="bg-white rounded-lg shadow p-4 flex items-center justify-between">
        <div>
          <h2 className="text-base font-semibold text-gray-700">数据库备份</h2>
          <p className="text-xs text-gray-400 mt-1">
            备份目录: <code className="text-gray-600 bg-gray-100 px-1 rounded">{backupDir || '未配置'}</code>
          </p>
          <p className="text-xs text-gray-400">
            保留策略: 最近 30 天，超期自动清理
          </p>
        </div>
        <button
          onClick={handleTriggerBackup}
          disabled={running}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {running ? '备份中...' : '触发备份'}
        </button>
      </section>

      {/* ── 备份列表 ── */}
      <section className="bg-white rounded-lg shadow">
        <div className="px-4 py-3 border-b border-gray-100">
          <h2 className="text-base font-semibold text-gray-700">
            备份列表
            <span className="ml-2 text-sm font-normal text-gray-400">共 {backups.length} 个</span>
          </h2>
        </div>

        {backups.length === 0 ? (
          <div className="text-center py-12 text-gray-400">
            <p className="text-lg mb-2">暂无备份文件</p>
            <p className="text-sm">点击"触发备份"按钮创建第一个备份</p>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-gray-500 text-left border-b">
                <th className="py-3 px-4 font-medium">文件名</th>
                <th className="py-3 px-4 font-medium">大小</th>
                <th className="py-3 px-4 font-medium">创建时间</th>
                <th className="py-3 px-4 font-medium">状态</th>
                <th className="py-3 px-4 font-medium">操作</th>
              </tr>
            </thead>
            <tbody>
              {backups.map((b) => (
                <tr key={b.filename} className="border-b last:border-b-0 hover:bg-gray-50">
                  <td className="py-3 px-4 font-mono text-xs text-gray-700 max-w-xs truncate" title={b.filename}>
                    {b.filename}
                  </td>
                  <td className="py-3 px-4 text-gray-600">{b.size_display}</td>
                  <td className="py-3 px-4 text-xs text-gray-500">
                    {b.created_at ? new Date(b.created_at).toLocaleString('zh-CN') : '-'}
                  </td>
                  <td className="py-3 px-4">
                    <StatusBadge status="success" />
                    <span className="ml-1 text-xs text-green-600">可用</span>
                  </td>
                  <td className="py-3 px-4">
                    <button
                      onClick={() => handleRestore(b.filename)}
                      disabled={restoring === b.filename}
                      className="px-3 py-1 bg-orange-500 text-white rounded text-xs hover:bg-orange-600 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {restoring === b.filename ? '恢复中...' : '恢复'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      {/* ── 使用说明 ── */}
      <section className="bg-white rounded-lg shadow p-4">
        <h2 className="text-base font-semibold text-gray-700 mb-2">命令行工具</h2>
        <div className="text-sm text-gray-600 space-y-2">
          <p>备份脚本和恢复脚本也支持在命令行使用:</p>
          <div className="bg-gray-900 text-green-300 font-mono text-xs rounded-lg p-3 space-y-1">
            <p># 执行备份</p>
            <p>python scripts/backup.py</p>
            <p className="mt-1"># 列出备份</p>
            <p>python scripts/backup.py --list</p>
            <p>python scripts/restore.py --list</p>
            <p className="mt-1"># 恢复到最新备份</p>
            <p>python scripts/restore.py --latest</p>
            <p className="mt-1"># 恢复到指定备份</p>
            <p>python scripts/restore.py --file backup_2026-06-01_120000.sql.gz</p>
            <p className="mt-1"># 模拟执行 (dry-run)</p>
            <p>python scripts/backup.py --dry-run</p>
          </div>
        </div>
      </section>
    </div>
  );
}

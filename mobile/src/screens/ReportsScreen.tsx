import React, { useCallback, useState } from 'react';
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  ActivityIndicator,
  RefreshControl,
  TouchableOpacity,
  Platform,
} from 'react-native';
import { useFocusEffect } from '@react-navigation/native';
import { fetchReports } from '../api/endpoints';
import type { ReportListItem } from '../types';

// Map report type to display labels
const REPORT_TYPE_LABELS: Record<string, string> = {
  roi_negative: 'ROI Negative Analysis',
  campaign_close: 'Campaign Close Summary',
};

export default function ReportsScreen() {
  const [reports, setReports] = useState<ReportListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [selectedReport, setSelectedReport] = useState<ReportListItem | null>(null);

  const loadData = useCallback(async () => {
    try {
      const data = await fetchReports();
      setReports(data);
    } catch (err) {
      console.warn('Failed to load reports:', err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      setLoading(true);
      loadData();
    }, [loadData])
  );

  const onRefresh = () => {
    setRefreshing(true);
    loadData();
  };

  if (loading && reports.length === 0) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" color="#1a73e8" />
      </View>
    );
  }

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
    >
      <Text style={styles.title}>Reports</Text>
      <Text style={styles.subtitle}>{reports.length} generated reports</Text>

      {reports.length === 0 && (
        <View style={styles.emptyState}>
          <Text style={styles.emptyText}>No reports generated yet. Reports are created automatically when system boundaries are triggered.</Text>
        </View>
      )}

      {reports.map((report) => (
        <TouchableOpacity
          key={report.id}
          style={styles.reportCard}
          onPress={() => setSelectedReport(selectedReport?.id === report.id ? null : report)}
        >
          <View style={styles.reportHeader}>
            <View style={styles.reportTypeBadge}>
              <Text style={styles.reportTypeText}>
                {REPORT_TYPE_LABELS[report.report_type] || report.report_type}
              </Text>
            </View>
            <Text style={styles.reportDate}>
              {new Date(report.created_at).toLocaleDateString()}
            </Text>
          </View>
          <Text style={styles.reportTitle}>{report.title}</Text>
          <Text style={styles.reportSku}>SKU: {report.sku_id}</Text>

          {selectedReport?.id === report.id && (
            <View style={styles.reportDetail}>
              <Text style={styles.detailLabel}>Content:</Text>
              <Text style={styles.detailText}>{JSON.stringify(report, null, 2)}</Text>
            </View>
          )}
        </TouchableOpacity>
      ))}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f7fa',
  },
  content: {
    padding: 20,
    paddingBottom: 40,
  },
  centered: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#f5f7fa',
  },
  title: {
    fontSize: 26,
    fontWeight: '800',
    color: '#222',
  },
  subtitle: {
    fontSize: 14,
    color: '#888',
    marginBottom: 16,
    marginTop: 2,
  },
  reportCard: {
    backgroundColor: '#fff',
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.06,
    shadowRadius: 3,
    elevation: 1,
  },
  reportHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  reportTypeBadge: {
    backgroundColor: '#e8f0fe',
    borderRadius: 6,
    paddingHorizontal: 8,
    paddingVertical: 3,
  },
  reportTypeText: {
    fontSize: 11,
    color: '#1a73e8',
    fontWeight: '600',
  },
  reportDate: {
    fontSize: 12,
    color: '#999',
  },
  reportTitle: {
    fontSize: 15,
    fontWeight: '600',
    color: '#333',
    marginBottom: 4,
  },
  reportSku: {
    fontSize: 12,
    color: '#999',
  },
  reportDetail: {
    marginTop: 12,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: '#f0f0f0',
  },
  detailLabel: {
    fontSize: 12,
    fontWeight: '600',
    color: '#666',
    marginBottom: 6,
  },
  detailText: {
    fontSize: 11,
    color: '#555',
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
    lineHeight: 16,
  },
  emptyState: {
    marginTop: 60,
    alignItems: 'center',
    paddingHorizontal: 20,
  },
  emptyText: {
    fontSize: 15,
    color: '#999',
    textAlign: 'center',
    lineHeight: 22,
  },
});

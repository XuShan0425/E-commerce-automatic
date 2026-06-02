import React, { useCallback, useEffect, useState } from 'react';
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  ActivityIndicator,
  RefreshControl,
} from 'react-native';
import { useFocusEffect } from '@react-navigation/native';
import MetricCard from '../components/MetricCard';
import { fetchDashboardSummary, type DashboardSummary } from '../api/endpoints';

export default function DashboardScreen() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const loadData = useCallback(async () => {
    try {
      const data = await fetchDashboardSummary();
      setSummary(data);
    } catch (err) {
      console.warn('Failed to load dashboard:', err);
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

  if (loading && !summary) {
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
      <Text style={styles.greeting}>Dashboard</Text>
      <Text style={styles.date}>{new Date().toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}</Text>

      <View style={styles.cardsRow}>
        <View style={styles.halfCard}>
          <MetricCard
            title="Average ROI"
            value={summary ? `${summary.averageRoi.toFixed(2)}%` : '--'}
            color={summary && summary.averageRoi >= 0 ? '#34a853' : '#d93025'}
          />
        </View>
        <View style={styles.halfCard}>
          <MetricCard
            title="Today's Ad Spend"
            value={summary ? `$${summary.todayAdSpend.toFixed(2)}` : '--'}
            color="#ea8600"
          />
        </View>
      </View>

      <View style={styles.cardsRow}>
        <View style={styles.halfCard}>
          <MetricCard
            title="Tracked Products"
            value={summary?.totalProducts ?? '--'}
            color="#1a73e8"
          />
        </View>
        <View style={styles.halfCard}>
          <MetricCard
            title="Active Alerts"
            value={summary?.activeAlerts ?? '--'}
            color={summary && summary.activeAlerts > 0 ? '#d93025' : '#34a853'}
          />
        </View>
      </View>

      {summary && summary.topProducts.length > 0 && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Top Products by ROI</Text>
          {summary.topProducts.map((p, i) => (
            <View key={p.sku_id} style={styles.productRow}>
              <Text style={styles.rank}>#{i + 1}</Text>
              <View style={styles.productInfo}>
                <Text style={styles.productName} numberOfLines={1}>{p.name}</Text>
                <Text style={styles.productSku}>{p.sku_id}</Text>
              </View>
              <Text style={[styles.roiValue, p.roi >= 0 ? styles.roiPositive : styles.roiNegative]}>
                {p.roi.toFixed(1)}%
              </Text>
            </View>
          ))}
        </View>
      )}

      {!summary && (
        <View style={styles.emptyState}>
          <Text style={styles.emptyText}>No data available. Ensure the server is running and API key is bound.</Text>
        </View>
      )}
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
  greeting: {
    fontSize: 26,
    fontWeight: '800',
    color: '#222',
  },
  date: {
    fontSize: 14,
    color: '#888',
    marginBottom: 20,
    marginTop: 2,
  },
  cardsRow: {
    flexDirection: 'row',
    gap: 10,
  },
  halfCard: {
    flex: 1,
  },
  section: {
    marginTop: 20,
    backgroundColor: '#fff',
    borderRadius: 14,
    padding: 16,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.06,
    shadowRadius: 4,
    elevation: 2,
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: '#333',
    marginBottom: 12,
  },
  productRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: '#f0f0f0',
  },
  rank: {
    fontSize: 14,
    fontWeight: '700',
    color: '#999',
    width: 30,
  },
  productInfo: {
    flex: 1,
    marginRight: 8,
  },
  productName: {
    fontSize: 14,
    fontWeight: '600',
    color: '#333',
  },
  productSku: {
    fontSize: 11,
    color: '#999',
    marginTop: 1,
  },
  roiValue: {
    fontSize: 15,
    fontWeight: '700',
  },
  roiPositive: {
    color: '#34a853',
  },
  roiNegative: {
    color: '#d93025',
  },
  emptyState: {
    marginTop: 40,
    alignItems: 'center',
  },
  emptyText: {
    fontSize: 14,
    color: '#999',
    textAlign: 'center',
    lineHeight: 20,
  },
});

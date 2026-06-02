import React from 'react';
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';

interface AlertItemProps {
  id: number;
  alertType: string;
  severity: string;
  message: string;
  isResolved: boolean;
  createdAt: string;
  onResolve?: (id: number) => void;
}

const SEVERITY_COLORS: Record<string, string> = {
  critical: '#d93025',
  high: '#ea8600',
  medium: '#f9ab00',
  low: '#1a73e8',
};

export default function AlertItem({
  id,
  alertType,
  severity,
  message,
  isResolved,
  createdAt,
  onResolve,
}: AlertItemProps) {
  const color = SEVERITY_COLORS[severity] || '#666';
  const dateStr = createdAt ? new Date(createdAt).toLocaleString() : '';

  return (
    <View style={[styles.container, isResolved && styles.resolved]}>
      <View style={[styles.severityBadge, { backgroundColor: color }]}>
        <Text style={styles.severityText}>{severity.toUpperCase()}</Text>
      </View>
      <View style={styles.content}>
        <Text style={styles.type}>{alertType}</Text>
        <Text style={styles.message}>{message}</Text>
        <Text style={styles.date}>{dateStr}</Text>
      </View>
      {!isResolved && onResolve && (
        <TouchableOpacity style={styles.resolveButton} onPress={() => onResolve(id)}>
          <Text style={styles.resolveText}>Resolve</Text>
        </TouchableOpacity>
      )}
      {isResolved && <Text style={styles.resolvedText}>Resolved</Text>}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    backgroundColor: '#fff',
    borderRadius: 10,
    padding: 14,
    marginBottom: 10,
    alignItems: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.06,
    shadowRadius: 3,
    elevation: 1,
  },
  resolved: {
    opacity: 0.6,
  },
  severityBadge: {
    borderRadius: 6,
    paddingHorizontal: 8,
    paddingVertical: 4,
    marginRight: 12,
  },
  severityText: {
    color: '#fff',
    fontSize: 10,
    fontWeight: '700',
  },
  content: {
    flex: 1,
  },
  type: {
    fontSize: 12,
    color: '#999',
    marginBottom: 2,
    fontWeight: '500',
  },
  message: {
    fontSize: 14,
    color: '#333',
    marginBottom: 4,
  },
  date: {
    fontSize: 11,
    color: '#aaa',
  },
  resolveButton: {
    backgroundColor: '#1a73e8',
    borderRadius: 8,
    paddingHorizontal: 14,
    paddingVertical: 8,
  },
  resolveText: {
    color: '#fff',
    fontSize: 13,
    fontWeight: '600',
  },
  resolvedText: {
    color: '#34a853',
    fontSize: 12,
    fontWeight: '600',
  },
});

import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

interface RealtimeUpdate {
  type: 'job_status_changed' | 'new_bid' | 'bid_updated' | 'job_assigned';
  data: {
    job_id: string;
    message: string;
    status?: string;
    bid_id?: string;
  };
}

export function useRealtimeUpdates() {
  const queryClient = useQueryClient();

  useEffect(() => {
    // Create WebSocket connection
    const ws = new WebSocket(
      `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws/jobs/`
    );

    ws.onopen = () => {
      console.log('Connected to job updates WebSocket');
    };

    ws.onmessage = (event) => {
      try {
        const update: RealtimeUpdate = JSON.parse(event.data);
        handleRealtimeUpdate(update);
      } catch (error) {
        console.error('Error parsing WebSocket message:', error);
      }
    };

    ws.onclose = () => {
      console.log('Disconnected from job updates WebSocket');
      // Attempt to reconnect after 3 seconds
      setTimeout(() => {
        console.log('Attempting to reconnect...');
        // You could implement reconnection logic here
      }, 3000);
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    const handleRealtimeUpdate = (update: RealtimeUpdate) => {
      switch (update.type) {
        case 'job_status_changed':
          queryClient.invalidateQueries({ queryKey: ["jobs"] });
          toast.info(`Job status updated: ${update.data.message}`);
          break;
          
        case 'new_bid':
          queryClient.invalidateQueries({ queryKey: ["bids", update.data.job_id] });
          queryClient.invalidateQueries({ queryKey: ["jobs"] });
          toast.success(`New bid received: ${update.data.message}`);
          break;
          
        case 'bid_updated':
          queryClient.invalidateQueries({ queryKey: ["bids", update.data.job_id] });
          toast.info(`Bid updated: ${update.data.message}`);
          break;
          
        case 'job_assigned':
          queryClient.invalidateQueries({ queryKey: ["jobs"] });
          toast.success(`Job assigned: ${update.data.message}`);
          break;
          
        default:
          console.log('Unknown update type:', update.type);
      }
    };

    // Cleanup WebSocket connection
    return () => {
      ws.close();
    };
  }, [queryClient]);
}
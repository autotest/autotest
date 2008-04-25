package afeclient.client;

import afeclient.client.table.RpcDataSource;

import com.google.gwt.json.client.JSONArray;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONString;
import com.google.gwt.json.client.JSONValue;

import java.util.Arrays;
import java.util.HashMap;
import java.util.Iterator;
import java.util.List;
import java.util.Map;

/**
 * Custom RpcDataSource to process the list of host queue entries for a job and
 * consolidate metahosts of the same label.
 */
class JobStatusDataSource extends RpcDataSource {
    public JobStatusDataSource() {
        super("get_host_queue_entries", "get_num_host_queue_entries");
    }
    
    protected JSONArray handleJsonResult(JSONValue result) {
        JSONArray rows = new JSONArray();
        Map metaHostCounts = new HashMap();
        JSONArray queueEntries = result.isArray();
        int count = 0;
        for(int i = 0; i < queueEntries.size(); i++) {
            JSONObject queueEntry = queueEntries.get(i).isObject();
            JSONValue host = queueEntry.get("host");
            String hostname, status;
            if (host.isNull() != null) {
                // metahost
                incrementMetaHostCount(metaHostCounts, queueEntry);
                continue;
            }
            
            // non-metahost - just insert the HostQueueEntry directly
            rows.set(rows.size(), queueEntry);
        }
        
        addMetaHostRows(metaHostCounts, rows);
        
        return rows;
    }
    
    protected void incrementMetaHostCount(Map metaHostCounts, JSONObject queueEntry) {
        String label = queueEntry.get("meta_host").isString().stringValue();
        String status = queueEntry.get("status").isString().stringValue();
        if (status.equals("Queued"))
            status = "Unassigned";
        List key = getMetaHostKey(label, status);
        
        int count = 0;
        if (metaHostCounts.containsKey(key))
            count = ((Integer) metaHostCounts.get(key)).intValue();
        metaHostCounts.put(key, new Integer(count + 1)); 
    }

    private List getMetaHostKey(String label, String status) {
        // arrays don't hash correctly, so use a list instead
        return Arrays.asList(new String[] {label, status});
    }
    
    protected void addMetaHostRows(Map metaHostCounts, JSONArray rows) {
        for(Iterator i = metaHostCounts.keySet().iterator(); i.hasNext(); ) {
            List key = (List) i.next();
            String label = (String) key.get(0), status = (String) key.get(1);
            int count = ((Integer) metaHostCounts.get(key)).intValue();
            JSONObject row = new JSONObject();
            row.put("host", new JSONString(label + " (label)"));
            row.put("status", new JSONString(Integer.toString(count) + 
                                             " " + status));
            rows.set(rows.size(), row);
        }
    }
}
package autotest.afe;

import autotest.common.StaticDataRepository;
import autotest.common.Utils;
import autotest.common.table.RpcDataSource;
import autotest.common.ui.NotifyManager;

import com.google.gwt.json.client.JSONArray;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONString;
import com.google.gwt.json.client.JSONValue;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * Custom RpcDataSource to process the list of host queue entries for a job and
 * consolidate metahosts of the same label.
 */
class JobStatusDataSource extends RpcDataSource {
    private JSONObject dictionary;

    public JobStatusDataSource() {
        super("get_host_queue_entries", "get_num_host_queue_entries");

        // retrieve the dictionary from static data
        StaticDataRepository staticData = StaticDataRepository.getRepository();
        dictionary = staticData.getData("status_dictionary").isObject();
    }

    private String translateStatus(String status)  {
        if (dictionary.containsKey(status)) {
            return dictionary.get(status).isString().stringValue();
        }
        else {
            NotifyManager.getInstance().showError("Unknown status", "Can not find status " +
                                                  status);
            return status;
        }
    }

    @Override
    protected List<JSONObject> handleJsonResult(JSONValue result) {
        List<JSONObject> queueEntries = super.handleJsonResult(result);
        List<JSONObject> rows = new ArrayList<JSONObject>();
        Map<List<String>, JSONObject> metaHostEntries= new HashMap<List<String>, JSONObject>();
        for(JSONObject queueEntry : queueEntries) {
            // translate status
            String status = queueEntry.get("status").isString().stringValue();
            String translation = translateStatus(status);
            queueEntry.put("status", new JSONString(translation));

            boolean hasHost = (queueEntry.get("host").isNull() == null);
            boolean hasMetaHost = (queueEntry.get("meta_host").isNull() == null);

            if (!hasHost && !hasMetaHost) {
                queueEntry.put("hostname", new JSONString("(hostless)"));
                rows.add(queueEntry);

            } else if (!hasHost && hasMetaHost) {
                // metahost
                incrementMetaHostCount(metaHostEntries, queueEntry);
            } else {
                // non-metahost
                processHostData(queueEntry);
                rows.add(queueEntry);
            }
        }

        addMetaHostRows(metaHostEntries, rows);

        return rows;
    }

    protected void processHostData(JSONObject queueEntry) {
        JSONObject host = queueEntry.get("host").isObject();
        queueEntry.put("hostname", host.get("hostname"));
        // don't show host details if the job is complete - it'll only confuse
        // the user
        boolean complete = queueEntry.get("complete").isBoolean().booleanValue();
        if (!complete) {
            queueEntry.put("host_status", host.get("status"));
            queueEntry.put("host_locked", AfeUtils.getLockedText(host));
        }
    }

    private void incrementMetaHostCount(Map<List<String>, JSONObject> metaHostEntries,
                                        JSONObject queueEntry) {
        String label = queueEntry.get("meta_host").isString().stringValue();
        String status = queueEntry.get("status").isString().stringValue();
        if (status.equals("Queued")) {
            status = "Unassigned";
        }
        List<String> key = getMetaHostKey(label, status);

        if (!metaHostEntries.containsKey(key)) {
            queueEntry.put("id_list", new JSONArray());
            metaHostEntries.put(key, queueEntry);
        }

        JSONObject metaHostEntry = metaHostEntries.get(key).isObject();
        JSONArray idList = metaHostEntry.get("id_list").isArray();
        idList.set(idList.size(), queueEntry.get("id"));
    }

    private List<String> getMetaHostKey(String label, String status) {
        // arrays don't hash correctly, so use a list instead
        return Arrays.asList(new String[] {label, status});
    }

    private void addMetaHostRows(Map<List<String>, JSONObject> metaHostEntries,
                                 List<JSONObject> rows) {
        for (JSONObject entry : metaHostEntries.values()) {
            String label = Utils.jsonToString(entry.get("meta_host"));
            String status = Utils.jsonToString(entry.get("status"));
            int count = entry.get("id_list").isArray().size();

            entry.put("hostname", new JSONString(label + " (label)"));
            entry.put("status", new JSONString(Integer.toString(count) + " " + status));
            rows.add(entry);
        }
    }
}

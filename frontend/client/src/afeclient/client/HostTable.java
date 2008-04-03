package afeclient.client;



import com.google.gwt.json.client.JSONArray;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONString;

import afeclient.client.table.DataSource;
import afeclient.client.table.DynamicTable;

public class HostTable extends DynamicTable {
    protected static final String LOCKED_TEXT = "locked_text";
    protected static final String OTHER_LABELS = "other_labels";
    public static final String[][] HOST_COLUMNS = {
            {"hostname", "Hostname"}, {"platform", "Platform"}, 
            {OTHER_LABELS, "Other labels"}, {"status", "Status"}, 
            {LOCKED_TEXT, "Locked"}
        };

    public HostTable(DataSource dataSource) {
        super(HOST_COLUMNS, dataSource);
    }

    protected void preprocessRow(JSONObject row) {
        super.preprocessRow(row);
        boolean locked = row.get("locked").isNumber().getValue() > 0;
        String lockedText = locked ? "Yes" : "No";
        row.put(LOCKED_TEXT, new JSONString(lockedText));
        
        JSONString jsonPlatform = row.get("platform").isString();
        String platform = "";
        if (jsonPlatform != null)
            platform = jsonPlatform.stringValue();
        JSONArray labels = row.get("labels").isArray();
        String labelString = "";
        for (int i = 0; i < labels.size(); i++) {
            String label = labels.get(i).isString().stringValue();
            if (label.equals(platform))
                continue;
            if (!labelString.equals(""))
                labelString += ", ";
            labelString += label;
        }
        row.put(OTHER_LABELS, new JSONString(labelString));
    }
}

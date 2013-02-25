package autotest.afe;

import autotest.common.Utils;
import autotest.common.table.DataSource;
import autotest.common.table.DynamicTable;

import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONString;

public class HostTable extends DynamicTable {
	private final int MAX_LABELS_COLUMN_WIDTH = 40;
	
    protected static final String[][] HOST_COLUMNS = {
        {"hostname", "Hostname"}, {"platform", "Platform"}, 
        {HostDataSource.OTHER_LABELS, "Other labels"}, {"status", "Status"}, 
        {HostDataSource.LOCKED_TEXT, "Locked"},
    };
    
    public HostTable(DataSource dataSource) {
        super(HOST_COLUMNS, dataSource);
    }

    public HostTable(String[][] columns, DataSource dataSource) {
        super(columns, dataSource);
    }
        
    @Override
    protected void preprocessRow(JSONObject host) {
    	// break labels column into separate lines if longer than some limit
    	String otherLabels = Utils.jsonToString(host.get(HostDataSource.OTHER_LABELS));
		host.put(HostDataSource.OTHER_LABELS, 
				new JSONString(Utils.splitIntoLines(otherLabels, MAX_LABELS_COLUMN_WIDTH)));
    }
}

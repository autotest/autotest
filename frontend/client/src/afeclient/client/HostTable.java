package afeclient.client;



import afeclient.client.table.DataSource;
import afeclient.client.table.DynamicTable;

public class HostTable extends DynamicTable {
    public static final String[][] HOST_COLUMNS = {
            {"hostname", "Hostname"}, {"platform", "Platform"}, 
            {HostDataSource.OTHER_LABELS, "Other labels"}, {"status", "Status"}, 
            {HostDataSource.LOCKED_TEXT, "Locked"}
        };

    public HostTable(DataSource dataSource) {
        super(HOST_COLUMNS, dataSource);
    }
}

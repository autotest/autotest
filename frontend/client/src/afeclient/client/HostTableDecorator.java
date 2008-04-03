package afeclient.client;

import afeclient.client.table.BooleanFilter;
import afeclient.client.table.ListFilter;
import afeclient.client.table.SearchFilter;
import afeclient.client.table.TableDecorator;

import com.google.gwt.json.client.JSONArray;

public class HostTableDecorator extends TableDecorator {
    protected SearchFilter hostnameFilter;
    protected ListFilter labelFilter, statusFilter;
    protected BooleanFilter lockedFilter;
    
    public HostTableDecorator(HostTable table, int rowsPerPage) {
        super(table);
        table.setRowsPerPage(rowsPerPage);
        addPaginators();
        
        StaticDataRepository staticData = StaticDataRepository.getRepository();
        JSONArray labels = staticData.getData("labels").isArray();
        String[] labelStrings = Utils.JSONtoStrings(labels);
        JSONArray statuses = staticData.getData("host_statuses").isArray();
        String[] statusStrings = Utils.JSONtoStrings(statuses);
        
        hostnameFilter = new SearchFilter("hostname");
        hostnameFilter.setExactMatch(false);
        labelFilter = new ListFilter("labels__name");
        labelFilter.setChoices(labelStrings);
        statusFilter = new ListFilter("status");
        statusFilter.setChoices(statusStrings);
        lockedFilter = new BooleanFilter("locked");
        
        addFilter("Hostname", hostnameFilter);
        addFilter("Label", labelFilter);
        addFilter("Status", statusFilter);
        addFilter("Locked", lockedFilter);
    }
}

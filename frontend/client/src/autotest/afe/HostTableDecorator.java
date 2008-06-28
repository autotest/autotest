package autotest.afe;

import autotest.common.StaticDataRepository;
import autotest.common.Utils;
import autotest.common.table.BooleanFilter;
import autotest.common.table.ListFilter;
import autotest.common.table.SearchFilter;
import autotest.common.table.TableDecorator;

import com.google.gwt.json.client.JSONArray;

public class HostTableDecorator extends TableDecorator {
    
    
    protected SearchFilter hostnameFilter;
    protected LabelFilter labelFilter;
    protected ListFilter statusFilter;
    protected BooleanFilter lockedFilter;
    
    public HostTableDecorator(HostTable table, int rowsPerPage) {
        super(table);
        table.setRowsPerPage(rowsPerPage);
        addPaginators();
        
        StaticDataRepository staticData = StaticDataRepository.getRepository();
        JSONArray statuses = staticData.getData("host_statuses").isArray();
        String[] statusStrings = Utils.JSONtoStrings(statuses);
        
        hostnameFilter = new SearchFilter("hostname");
        hostnameFilter.setExactMatch(false);
        labelFilter = new LabelFilter();
        statusFilter = new ListFilter("status");
        statusFilter.setChoices(statusStrings);
        lockedFilter = new BooleanFilter("locked");
        
        addFilter("Hostname", hostnameFilter);
        addControl("Platform", labelFilter.getPlatformWidget());
        addFilter("Label", labelFilter);
        addFilter("Status", statusFilter);
        addFilter("Locked", lockedFilter);
    }
}

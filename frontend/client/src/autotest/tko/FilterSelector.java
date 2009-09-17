package autotest.tko;

import autotest.common.Utils;
import autotest.common.ui.ExtendedListBox;
import autotest.common.ui.SimpleHyperlink;
import autotest.tko.FilterStringViewer.EditListener;

import com.google.gwt.event.dom.client.ChangeEvent;
import com.google.gwt.event.dom.client.ChangeHandler;
import com.google.gwt.event.dom.client.ClickEvent;
import com.google.gwt.event.dom.client.ClickHandler;
import com.google.gwt.user.client.ui.Composite;
import com.google.gwt.user.client.ui.FlexTable;
import com.google.gwt.user.client.ui.HasHorizontalAlignment;
import com.google.gwt.user.client.ui.HorizontalPanel;
import com.google.gwt.user.client.ui.Panel;
import com.google.gwt.user.client.ui.RadioButton;
import com.google.gwt.user.client.ui.TextBox;
import com.google.gwt.user.client.ui.VerticalPanel;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

public class FilterSelector extends Composite {
    
    public class DatabaseFilter extends Composite implements ChangeHandler {
        
        private ExtendedListBox dbColumnSelector = new DBColumnSelector(dbView);
        private TextBox condition = new TextBox();
        private FlexTable flexTable = new FlexTable();
        private SimpleHyperlink deleteLink = new SimpleHyperlink("[X]");
        
        private DatabaseFilter() {
            dbColumnSelector.addChangeHandler(this);
            condition.addChangeHandler(this);
            
            deleteLink.addClickHandler(new ClickHandler() {
                public void onClick(ClickEvent event) {
                    if (enabled) {
                        deleteFilter(DatabaseFilter.this);
                        buildFilterString();
                    }
                }
            });
            
            flexTable.setWidget(0, 0, dbColumnSelector);
            flexTable.setWidget(0, 1, condition);
            flexTable.setWidget(0, 2, deleteLink);
            
            initWidget(flexTable);
        }
        
        @Override
        public void onChange(ChangeEvent event) {
            buildFilterString();
        }
        
        public void setEnabled(boolean enabled) {
            dbColumnSelector.setEnabled(enabled);
            condition.setEnabled(enabled);
        }
        
        public boolean isEmpty() {
            return condition.getText().equals("");
        }
        
        public String getFilterString() {
            return dbColumnSelector.getSelectedValue() + " " + condition.getText();
        }
    }
    
    private FlexTable table = new FlexTable();
    private Panel filtersPanel = new VerticalPanel();
    private List<DatabaseFilter> filters = new ArrayList<DatabaseFilter>();
    private RadioButton all;
    private RadioButton any;
    private SimpleHyperlink addLink = new SimpleHyperlink("[Add Filter]");
    private FilterStringViewer viewer = new FilterStringViewer();
    private boolean enabled = true;
    private String dbView;
    private static int filterSelectorId;

    public FilterSelector(String dbView) {
        this.dbView = dbView;
        int id = filterSelectorId;
        filterSelectorId++;
        
        all = new RadioButton("booleanOp" + id, "all of");
        any = new RadioButton("booleanOp" + id, "any of");
        
        ClickHandler booleanOpListener = new ClickHandler() {
            public void onClick(ClickEvent event) {
                buildFilterString();
            }
        };
        all.addClickHandler(booleanOpListener);
        any.addClickHandler(booleanOpListener);
        all.setValue(true);

        addLink.addClickHandler(new ClickHandler() {
            public void onClick(ClickEvent event) {
                if (enabled) {
                    addFilter();
                }
            }
        });

        viewer.addEditListener(new EditListener() {
            public void onEdit() {
                setEnabled(false);
            }
            
            public void onRevert() {
                setEnabled(true);
                buildFilterString();
            }
        });
        
        Panel booleanOpPanel = new HorizontalPanel();
        booleanOpPanel.add(all);
        booleanOpPanel.add(any);
        table.setWidget(0, 0, booleanOpPanel);
        table.setWidget(1, 0, filtersPanel);
        table.getFlexCellFormatter().setColSpan(1, 0, 2);
        table.setWidget(2, 1, addLink);
        table.getFlexCellFormatter().setHorizontalAlignment(
                2, 1, HasHorizontalAlignment.ALIGN_RIGHT);
        table.setWidget(3, 0, viewer);
        table.getFlexCellFormatter().setColSpan(3, 0, 2);
        table.setStylePrimaryName("box");
        
        addFilter();
        
        initWidget(table);
    }
    
    public String getFilterString() {
        return viewer.getText();
    }
    
    public void reset() {
        filtersPanel.clear();
        filters.clear();
        addFilter();
    }
    
    protected void addToHistory(Map<String, String> args, String prefix) {
        // Get all the filters/conditions
        for (int index = 0; index < filters.size(); index++) {
            args.put(prefix + "[" + index + "][db]",
                    filters.get(index).dbColumnSelector.getSelectedValue());
            args.put(prefix + "[" + index + "][condition]", filters.get(index).condition.getText());
        }
        
        // Get whether the filter should be "all" or "any"
        args.put(prefix + "_all", Boolean.toString(all.getValue()));
        
        viewer.addToHistory(args, prefix);
    }
    
    protected void handleHistoryArguments(Map<String, String> args, String prefix) {
        int index = 0;
        String db, condition;
        
        // Restore all the filters/conditions
        while ((db = args.get(prefix + "[" + index + "][db]")) != null) {
            condition = args.get(prefix + "[" + index + "][condition]");
            DatabaseFilter filter;
            if (index == 0) {
                filter = filters.get(0);
            } else {
                filter = addFilter();
            }
            filter.dbColumnSelector.selectByValue(db);
            filter.condition.setText(condition);
            index++;
        }
        
        // Restore the "all" or "any" selection
        boolean allChecked = Boolean.parseBoolean(args.get(prefix + "_all"));
        if (allChecked) {
            all.setValue(true);
        } else {
            any.setValue(true);
        }
        
        buildFilterString();
        viewer.handleHistoryArguments(args, prefix);
    }
    
    private DatabaseFilter addFilter() {
        DatabaseFilter nextFilter = new DatabaseFilter();
        filters.add(nextFilter);
        filtersPanel.add(nextFilter);
        return nextFilter;
    }
    
    private void deleteFilter(DatabaseFilter filter) {
        // If there's only one filter, clear it
        if (filters.size() == 1) {
            reset();
            return;
        }
        
        filters.remove(filter);
        filtersPanel.remove(filter);
    }
    
    private void setEnabled(boolean enabled) {
        this.enabled = enabled;
        all.setEnabled(enabled);
        any.setEnabled(enabled);
        for (DatabaseFilter filter : filters) {
            filter.setEnabled(enabled);
        }
    }
    
    private void buildFilterString() {
        List<String> filterParts = new ArrayList<String>();
        for (DatabaseFilter filter : filters) {
            if (!filter.isEmpty()) {
                filterParts.add(filter.getFilterString());
            }
        }

        String joiner = all.getValue() ? " AND " : " OR ";
        String fullFilterString = Utils.joinStrings(joiner, filterParts);
        viewer.setText(fullFilterString);
    }
}

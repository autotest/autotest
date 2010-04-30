package autotest.planner.triage;

import com.google.gwt.event.dom.client.HasClickHandlers;
import com.google.gwt.gen2.table.client.FixedWidthFlexTable;
import com.google.gwt.gen2.table.client.FixedWidthGrid;
import com.google.gwt.gen2.table.client.ScrollTable;
import com.google.gwt.gen2.table.client.AbstractScrollTable.ResizePolicy;
import com.google.gwt.gen2.table.client.AbstractScrollTable.ScrollPolicy;
import com.google.gwt.gen2.table.client.AbstractScrollTable.SortPolicy;
import com.google.gwt.gen2.table.client.SelectionGrid.SelectionPolicy;
import com.google.gwt.gen2.table.override.client.FlexTable.FlexCellFormatter;
import com.google.gwt.user.client.ui.CheckBox;
import com.google.gwt.user.client.ui.Composite;
import com.google.gwt.user.client.ui.HasValue;

import java.util.Set;


public class FailureTableDisplay extends Composite implements FailureTable.Display {
    
    private FixedWidthFlexTable header = new FixedWidthFlexTable();
    private FixedWidthGrid dataTable;
    private ScrollTable scrollTable;
    private CheckBox selectAll = new CheckBox();
    
    public FailureTableDisplay(String group, String[] columnNames) {
        FlexCellFormatter formatter = header.getFlexCellFormatter();
        
        dataTable = new FixedWidthGrid(0, columnNames.length);
        dataTable.setSelectionPolicy(SelectionPolicy.CHECKBOX);
        
        scrollTable = new ScrollTable(dataTable, header);
        scrollTable.setSortPolicy(SortPolicy.DISABLED);
        scrollTable.setResizePolicy(ResizePolicy.UNCONSTRAINED);
        scrollTable.setScrollPolicy(ScrollPolicy.BOTH);
        scrollTable.setHeight("200px");
        
        header.setText(0, 0, group);
        header.setWidget(1, 0, selectAll);
        
        formatter.setColSpan(0, 0, columnNames.length + 1);
        for (int i = 0; i < columnNames.length; i++) {
            header.setText(1, i + 1, columnNames[i]);
        }
        
        initWidget(scrollTable);
    }
    
    @Override
    public void addRow(String[] cells, boolean isNew) {
        assert dataTable.getColumnCount() == cells.length;
        
        int row = dataTable.getRowCount();
        dataTable.resizeRows(row + 1);
        for (int cell = 0; cell < cells.length; cell++) {
            dataTable.setText(row, cell, cells[cell]);
        }
        
        for (int column = 0; column < dataTable.getColumnCount(); column++) {
            int width = Math.max(
                      dataTable.getIdealColumnWidth(column), header.getColumnWidth(column + 1));
            
            header.setColumnWidth(column + 1, width);
            dataTable.setColumnWidth(column, width);
        }
    }

    @Override
    public HasClickHandlers getSelectAllControl() {
        return selectAll;
    }

    @Override
    public HasValue<Boolean> getSelectAllValue() {
        return selectAll;
    }

    public void setAllRowsSelected(boolean selected) {
        if (selected) {
            dataTable.selectAllRows();
        } else {
            dataTable.deselectAllRows();
        }
    }

    @Override
    public Set<Integer> getSelectedFailures() {
        return dataTable.getSelectedRows();
    }
}

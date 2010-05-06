package autotest.planner.triage;

import autotest.planner.TestPlannerUtils;

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

    private String group;

    public FailureTableDisplay(String group, String[] columnNames) {
        this.group = group;


        dataTable = new FixedWidthGrid(0, columnNames.length);
        dataTable.setSelectionPolicy(SelectionPolicy.CHECKBOX);

        scrollTable = new ScrollTable(dataTable, header);
        scrollTable.setSortPolicy(SortPolicy.DISABLED);
        scrollTable.setResizePolicy(ResizePolicy.UNCONSTRAINED);
        scrollTable.setScrollPolicy(ScrollPolicy.BOTH);
        scrollTable.setHeight("200px");

        header.setWidget(1, 0, selectAll);

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
    }

    @Override
    public void finalRender() {
        TestPlannerUtils.resizeScrollTable(scrollTable, true);

        /*
         * Add the group header and redraw the table after the column resizing. This is to work
         * around a bug (feature?) where getIdealColumnWidth() computes weird numbers for ideal
         * width when there's a colspan'd column.
         */
        header.setText(0, 0, group);
        FlexCellFormatter formatter = header.getFlexCellFormatter();
        formatter.setColSpan(0, 0, header.getColumnCount());

        scrollTable.redraw();
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

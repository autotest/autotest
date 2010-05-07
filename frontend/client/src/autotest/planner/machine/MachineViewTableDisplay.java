package autotest.planner.machine;

import autotest.planner.TestPlannerUtils;
import autotest.planner.machine.MachineViewTable.RowDisplay;

import com.google.gwt.event.logical.shared.ResizeEvent;
import com.google.gwt.event.logical.shared.ResizeHandler;
import com.google.gwt.gen2.table.client.FixedWidthFlexTable;
import com.google.gwt.gen2.table.client.FixedWidthGrid;
import com.google.gwt.gen2.table.client.ScrollTable;
import com.google.gwt.gen2.table.client.AbstractScrollTable.ResizePolicy;
import com.google.gwt.gen2.table.client.AbstractScrollTable.ScrollPolicy;
import com.google.gwt.gen2.table.client.AbstractScrollTable.SortPolicy;
import com.google.gwt.user.client.Window;
import com.google.gwt.user.client.ui.Composite;

import java.util.Collection;

public class MachineViewTableDisplay extends Composite
        implements MachineViewTable.Display, ResizeHandler {

    private FixedWidthFlexTable headerTable = new FixedWidthFlexTable();
    private FixedWidthGrid dataTable = new FixedWidthGrid();
    private ScrollTable scrollTable = new ScrollTable(dataTable, headerTable);

    public MachineViewTableDisplay() {
        scrollTable.setSortPolicy(SortPolicy.DISABLED);
        scrollTable.setResizePolicy(ResizePolicy.UNCONSTRAINED);
        scrollTable.setScrollPolicy(ScrollPolicy.BOTH);
        dataTable.setSelectionEnabled(false);

        scrollTable.setSize("100%", TestPlannerUtils.getHeightParam(Window.getClientHeight()));
        scrollTable.setVisible(false);

        initWidget(scrollTable);
    }

    @Override
    public void addRow(Collection<RowDisplay> rowData) {
        assert rowData.size() == dataTable.getColumnCount();

        int row = dataTable.insertRow(dataTable.getRowCount());

        int column = 0;
        for (RowDisplay data : rowData) {
            dataTable.setText(row, column, data.content);
            dataTable.getCellFormatter().addStyleName(row, column++, data.cssClass);
        }
    }

    @Override
    public void finalRender() {
        TestPlannerUtils.resizeScrollTable(scrollTable);
    }

    @Override
    public void clearData() {
        scrollTable.setVisible(false);
        headerTable.clear();
        dataTable.clear();
    }

    @Override
    public void setHeaders(Collection<String> headers) {
        int column = 0;
        for (String header : headers) {
            headerTable.setText(0, column, header);
            scrollTable.setHeaderColumnTruncatable(column++, false);
        }

        dataTable.resize(0, headers.size());

        scrollTable.setVisible(true);
    }

    @Override
    public void onResize(ResizeEvent event) {
        scrollTable.setHeight(TestPlannerUtils.getHeightParam(event.getHeight()));
    }
}

package autotest.planner;

import autotest.common.Utils;

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

public class TestPlannerTableImpl extends Composite
        implements TestPlannerTableDisplay, ResizeHandler {

    private FixedWidthFlexTable headerTable = new FixedWidthFlexTable();
    private FixedWidthGrid dataTable = new FixedWidthGrid();
    private ScrollTable scrollTable = new ScrollTable(dataTable, headerTable);

    public TestPlannerTableImpl() {
        scrollTable.setSortPolicy(SortPolicy.DISABLED);
        scrollTable.setResizePolicy(ResizePolicy.UNCONSTRAINED);
        scrollTable.setScrollPolicy(ScrollPolicy.BOTH);
        dataTable.setSelectionEnabled(false);

        scrollTable.setSize("100%", TestPlannerUtils.getHeightParam(Window.getClientHeight()));
        scrollTable.setVisible(false);

        initWidget(scrollTable);
    }

    public void addRow(Collection<RowDisplay> rowData) {
        assert rowData.size() == dataTable.getColumnCount();

        int row = dataTable.insertRow(dataTable.getRowCount());

        int column = 0;
        for (RowDisplay data : rowData) {
            String content = Utils.escape(data.content);
            content = content.replaceAll("\n", "<br />");

            dataTable.setHTML(row, column, content);
            dataTable.getCellFormatter().addStyleName(row, column++, data.cssClass);
        }
    }

    public void finalRender() {
        TestPlannerUtils.resizeScrollTable(scrollTable);
    }

    public void clearData() {
        scrollTable.setVisible(false);
        headerTable.clear();
        dataTable.clear();
    }

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

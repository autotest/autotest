package autotest.common.table;

import autotest.common.ui.Paginator;

import com.google.gwt.user.client.ui.Composite;
import com.google.gwt.user.client.ui.FlexTable;
import com.google.gwt.user.client.ui.HasHorizontalAlignment;
import com.google.gwt.user.client.ui.Widget;

public class TableDecorator extends Composite {
    protected FlexTable enclosingTable = new FlexTable();
    protected DynamicTable dataTable;
    protected int numFilters = 0;
    
    public TableDecorator(DynamicTable dataTable) {
        this.dataTable = dataTable;
        fillDoubleCell(0, 0, dataTable, false);
        initWidget(enclosingTable);
    }
    
    public void addPaginators() {
        for(int i = 0; i < 2; i++) {
            Paginator p = new Paginator();
            dataTable.attachPaginator(p);
            if (i == 0) { // add at top
                enclosingTable.insertRow(numFilters);
                fillDoubleCell(numFilters, 0, p, true);
            }
            else { // add at bottom
                fillDoubleCell(numFilters + 2, 0, p, true);
            }
        }
    }
    
    public void addFilter(String text, Filter filter) {
        dataTable.addFilter(filter);
        addControl(text, filter.getWidget());
    }
    
    protected void addControl(String text, Widget widget) {
      enclosingTable.insertRow(numFilters);
      int row = numFilters;
      numFilters++;
      enclosingTable.setText(row, 0, text);
      enclosingTable.setWidget(row, 1, widget);
    }
    
    protected void fillDoubleCell(int row, int col, Widget widget, 
                                  boolean center) {
        enclosingTable.setWidget(row, col, widget);
        enclosingTable.getFlexCellFormatter().setColSpan(row, col, 2);
        if (center)
            enclosingTable.getCellFormatter().setHorizontalAlignment(
                                 row, col, HasHorizontalAlignment.ALIGN_CENTER);
    }
}

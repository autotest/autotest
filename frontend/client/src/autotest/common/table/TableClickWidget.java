package autotest.common.table;

import com.google.gwt.user.client.ui.ClickListener;
import com.google.gwt.user.client.ui.Composite;
import com.google.gwt.user.client.ui.FocusWidget;
import com.google.gwt.user.client.ui.Widget;


public class TableClickWidget extends Composite implements ClickListener {
    
    private FocusWidget widget;
    private TableWidgetClickListener listener;
    private int row;
    private int cell;

    public static interface TableWidgetClickListener {
        public void onClick(TableClickWidget widget);
    }
    
    public TableClickWidget(FocusWidget widget, TableWidgetClickListener listener, 
                            int row, int cell) {
        this.widget = widget;
        this.row = row;
        this.cell = cell;
        this.listener = listener;
 
        initWidget(widget);
        widget.addClickListener(this);
    }
    
    public void onClick(Widget sender) {
        listener.onClick(this);
    }
    
    public int getRow() {
        return row;
    }
    
    public int getCell() {
        return cell;
    }
    
    public FocusWidget getContainedWidget() {
        return widget;
    }
}

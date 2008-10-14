package autotest.common.ui;

import com.google.gwt.user.client.ui.ClickListener;
import com.google.gwt.user.client.ui.Composite;
import com.google.gwt.user.client.ui.HTML;
import com.google.gwt.user.client.ui.HorizontalPanel;
import com.google.gwt.user.client.ui.Panel;
import com.google.gwt.user.client.ui.Widget;

public class TableSelectionPanel extends Composite implements ClickListener {
    public static interface SelectionPanelListener {
        public void onSelectAll(boolean visibleOnly);
        public void onSelectNone();
    }

    private SelectionPanelListener listener;
    private SimpleHyperlink selectAll = new SimpleHyperlink("all");
    private SimpleHyperlink selectVisible;
    private SimpleHyperlink selectNone = new SimpleHyperlink("none");
    
    public TableSelectionPanel(boolean wantSelectVisible) {
        selectAll.addClickListener(this);
        selectNone.addClickListener(this);
        
        Panel selectPanel = new HorizontalPanel();
        selectPanel.add(new HTML("Select:&nbsp;"));
        selectPanel.add(selectAll);
        selectPanel.add(new HTML(",&nbsp;"));
        if (wantSelectVisible) {
            selectVisible = new SimpleHyperlink("visible");
            selectVisible.addClickListener(this);
            selectPanel.add(selectVisible);
            selectPanel.add(new HTML(",&nbsp;"));
        }
        selectPanel.add(selectNone);
        selectPanel.add(new HTML("&nbsp;"));
        initWidget(selectPanel);
    }
    
    public void setListener(SelectionPanelListener listener) {
        this.listener = listener;
    }

    public void onClick(Widget sender) {
        if (sender == selectAll) {
            listener.onSelectAll(false);
        } else if (sender == selectVisible) {
            listener.onSelectAll(true);
        } else {
            assert sender == selectNone;
            listener.onSelectNone();
        }
    }
}

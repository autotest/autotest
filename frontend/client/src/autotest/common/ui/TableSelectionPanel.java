package autotest.common.ui;

import com.google.gwt.event.dom.client.ClickEvent;
import com.google.gwt.event.dom.client.ClickHandler;
import com.google.gwt.user.client.ui.Anchor;
import com.google.gwt.user.client.ui.Composite;
import com.google.gwt.user.client.ui.HTML;
import com.google.gwt.user.client.ui.HorizontalPanel;
import com.google.gwt.user.client.ui.Panel;

public class TableSelectionPanel extends Composite implements ClickHandler {
    public static interface SelectionPanelListener {
        public void onSelectAll(boolean visibleOnly);
        public void onSelectNone();
    }

    private SelectionPanelListener listener;
    private Anchor selectAll = new Anchor("all");
    private Anchor selectVisible;
    private Anchor selectNone = new Anchor("none");

    public TableSelectionPanel(boolean wantSelectVisible) {
        selectAll.addClickHandler(this);
        selectNone.addClickHandler(this);

        Panel selectPanel = new HorizontalPanel();
        selectPanel.add(new HTML("Select:&nbsp;"));
        selectPanel.add(selectAll);
        selectPanel.add(new HTML(",&nbsp;"));
        if (wantSelectVisible) {
            selectVisible = new Anchor("visible");
            selectVisible.addClickHandler(this);
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

    public void onClick(ClickEvent event) {
        if (event.getSource() == selectAll) {
            listener.onSelectAll(false);
        } else if (event.getSource() == selectVisible) {
            listener.onSelectAll(true);
        } else {
            assert event.getSource() == selectNone;
            listener.onSelectNone();
        }
    }
}

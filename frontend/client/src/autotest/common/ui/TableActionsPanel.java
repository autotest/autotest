package autotest.common.ui;


import autotest.common.ui.TableSelectionPanel.SelectionPanelListener;

import com.google.gwt.user.client.ui.ClickListener;
import com.google.gwt.user.client.ui.Composite;
import com.google.gwt.user.client.ui.HorizontalPanel;
import com.google.gwt.user.client.ui.Panel;
import com.google.gwt.user.client.ui.PopupListener;
import com.google.gwt.user.client.ui.PopupPanel;
import com.google.gwt.user.client.ui.ToggleButton;
import com.google.gwt.user.client.ui.Widget;

public class TableActionsPanel extends Composite implements ClickListener, PopupListener {
    public static interface TableActionsListener {
        public ContextMenu getActionMenu();
    }

    private TableActionsListener listener;
    private ToggleButton actionsButton = new ToggleButton("Actions");
    private TableSelectionPanel selectionPanel;
    
    public TableActionsPanel(boolean wantSelectVisible) {
        selectionPanel = new TableSelectionPanel(wantSelectVisible);
        actionsButton.addClickListener(this);

        Panel mainPanel = new HorizontalPanel();
        mainPanel.add(selectionPanel);
        mainPanel.add(actionsButton);
        initWidget(mainPanel);
    }
    
    public void setActionsListener(TableActionsListener listener) {
        this.listener = listener;
    }
    
    public void setSelectionListener(SelectionPanelListener listener) {
        selectionPanel.setListener(listener);
    }
    
    public void onClick(Widget sender) {
        assert sender == actionsButton;
        ContextMenu menu = listener.getActionMenu();
        menu.addPopupListener(this);
        menu.showAt(actionsButton.getAbsoluteLeft(), 
                    actionsButton.getAbsoluteTop() + actionsButton.getOffsetHeight());
    }

    public void onPopupClosed(PopupPanel sender, boolean autoClosed) {
        actionsButton.setDown(false);
    }
}

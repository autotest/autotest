package autotest.common.ui;


import com.google.gwt.user.client.ui.ClickListener;
import com.google.gwt.user.client.ui.Composite;
import com.google.gwt.user.client.ui.HTML;
import com.google.gwt.user.client.ui.HorizontalPanel;
import com.google.gwt.user.client.ui.Panel;
import com.google.gwt.user.client.ui.PopupListener;
import com.google.gwt.user.client.ui.PopupPanel;
import com.google.gwt.user.client.ui.ToggleButton;
import com.google.gwt.user.client.ui.Widget;

public class TableActionsPanel extends Composite implements ClickListener, PopupListener {
    public static interface TableActionsListener {
        public ContextMenu getActionMenu();
        public void onSelectAll();
        public void onSelectNone();
    }

    private TableActionsListener listener;
    private ToggleButton actionsButton = new ToggleButton("Actions");
    private SimpleHyperlink selectAll = new SimpleHyperlink("all");
    private SimpleHyperlink selectNone = new SimpleHyperlink("none");
    
    public TableActionsPanel(TableActionsListener tableActionsListener) {
        listener = tableActionsListener;
        
        actionsButton.addClickListener(this);
        selectAll.addClickListener(this);
        selectNone.addClickListener(this);
        
        Panel selectPanel = new HorizontalPanel();
        selectPanel.add(new HTML("Select:&nbsp;"));
        selectPanel.add(selectAll);
        selectPanel.add(new HTML(",&nbsp;"));
        selectPanel.add(selectNone);
        selectPanel.add(new HTML("&nbsp;"));
        selectPanel.add(actionsButton);
        initWidget(selectPanel);
    }
    
    public void onClick(Widget sender) {
        if (sender == actionsButton) {
            ContextMenu menu = listener.getActionMenu();
            menu.addPopupListener(this);
            menu.showAt(actionsButton.getAbsoluteLeft(), 
                        actionsButton.getAbsoluteTop() + actionsButton.getOffsetHeight());
        } else if (sender == selectAll) {
            listener.onSelectAll();
        } else {
            assert sender == selectNone;
            listener.onSelectNone();
        }
    }

    public void onPopupClosed(PopupPanel sender, boolean autoClosed) {
        actionsButton.setDown(false);
    }
}

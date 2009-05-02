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
    
    public static interface TableActionsWithExportCsvListener extends TableActionsListener {
        public void onExportCsv();
    }

    private TableActionsListener listener;
    private TableActionsWithExportCsvListener csvListener;
    private ToggleButton actionsButton = new ToggleButton("Actions");
    private TableSelectionPanel selectionPanel;
    private SimpleHyperlink exportCsvLink = new SimpleHyperlink("Export to CSV");
    
    public TableActionsPanel(boolean wantSelectVisible) {
        selectionPanel = new TableSelectionPanel(wantSelectVisible);
        actionsButton.addClickListener(this);
        exportCsvLink.addClickListener(this);
        exportCsvLink.setVisible(false);
        exportCsvLink.getElement().getStyle().setProperty("marginLeft", "1em");

        Panel mainPanel = new HorizontalPanel();
        mainPanel.add(selectionPanel);
        mainPanel.add(actionsButton);
        mainPanel.add(exportCsvLink);
        initWidget(mainPanel);
    }
    
    public void setActionsListener(TableActionsListener listener) {
        this.listener = listener;
    }
    
    /**
     * This automatically enables the Export CSV link, which is disabled by default.
     */
    public void setActionsWithCsvListener(TableActionsWithExportCsvListener listener) {
        csvListener = listener;
        this.listener = listener;
        exportCsvLink.setVisible(true);
    }
    
    public void setSelectionListener(SelectionPanelListener listener) {
        selectionPanel.setListener(listener);
    }
    
    public void onClick(Widget sender) {
        if (sender == exportCsvLink) {
            assert csvListener != null;
            csvListener.onExportCsv();
        } else {
            assert sender == actionsButton;
            ContextMenu menu = listener.getActionMenu();
            menu.addPopupListener(this);
            menu.showAt(actionsButton.getAbsoluteLeft(), 
                        actionsButton.getAbsoluteTop() + actionsButton.getOffsetHeight());
        }
    }

    public void onPopupClosed(PopupPanel sender, boolean autoClosed) {
        actionsButton.setDown(false);
    }
}

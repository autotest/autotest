package autotest.common.ui;

import com.google.gwt.event.logical.shared.CloseHandler;
import com.google.gwt.user.client.Command;
import com.google.gwt.user.client.Window;
import com.google.gwt.user.client.ui.MenuBar;
import com.google.gwt.user.client.ui.MenuItem;
import com.google.gwt.user.client.ui.PopupPanel;



public class ContextMenu {
    private  PopupPanel popup = new PopupPanel(true);
    private MenuBar menu = new AutoHideMenu();
    
    private class CommandWrapper implements Command {
        private Command command;
        
        CommandWrapper(Command command) {
            this.command = command;
        }
        
        public void execute() {
            popup.hide();
            command.execute();
        }
    }

    private class AutoHideMenu extends MenuBar {
        public AutoHideMenu() {
            super(true);
        }
        
        @Override
        public MenuItem addItem(String text, Command cmd) {
            return super.addItem(text, new CommandWrapper(cmd));
        }
    }

    public ContextMenu() {
        menu.setAutoOpen(true);
        popup.add(menu);
    }
    
    public void useHandCursor() {
        menu.addStyleName("menubar-hand-cursor");
    }

    public void addItem(String text, Command cmd) {
        menu.addItem(text, new CommandWrapper(cmd));
    }

    public MenuBar addSubMenuItem(String text) {
        MenuBar subMenu = new AutoHideMenu();
        menu.addItem(text, subMenu);
        return subMenu;
    }

    public void showAt(int left, int top) {
        popup.setPopupPosition(left, top);
        popup.show();
    }

    public void showAtWindow(int left, int top) {
        showAt(left + Window.getScrollLeft(), top + Window.getScrollTop());
    }

    public void addCloseHandler(CloseHandler<PopupPanel> closeHandler) {
        popup.addCloseHandler(closeHandler);
    }

}
